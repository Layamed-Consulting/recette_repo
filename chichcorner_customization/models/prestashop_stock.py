from odoo import models, api, fields
import requests
from xml.etree import ElementTree as ET
import logging
import time
from datetime import datetime, timedelta
_logger = logging.getLogger(__name__)

class PrestashopStockCron(models.Model):
    _name = 'prestashop.stock.cron'
    _description = 'Cron job to update Prestashop stock'

    # Add field to track where we left off
    last_processed_index = fields.Integer(default=0, help="Last processed product index")

    @api.model
    def update_prestashop_stock_via_products(self):
        """Sync stock using products API to get EAN13 and stock_availables IDs"""
        BASE_URL = "https://www.premiumshop.ma/api"
        WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"
        headers = {'Content-Type': 'application/xml'}

        # Get or create singleton record to track progress
        sync_record = self.search([], limit=1)
        if not sync_record:
            sync_record = self.create({'last_processed_index': 0})

        # Time limit: 90 seconds (30 seconds buffer before Odoo's 120s limit)
        start_time = time.time()
        TIME_LIMIT = 90

        def get_xml(url):
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    _logger.warning(f"GET failed: {url} | Status: {resp.status_code}")
                    return None
                return ET.fromstring(resp.content)
            except Exception as e:
                _logger.warning(f"Exception during GET: {url} | Error: {e}")
                return None

        def put_xml(url, data):
            try:
                resp = requests.put(url, data=data, headers=headers, timeout=30)
                if resp.status_code not in (200, 201):
                    _logger.warning(f"PUT failed: {url} | Status: {resp.status_code}")
                    return None
                return resp
            except Exception as e:
                _logger.warning(f"Exception during PUT: {url} | Error: {e}")
                return None

        def get_products_with_pagination(start=0, limit=50):
            """Get products with pagination"""
            try:
                products_url = f"{BASE_URL}/products?ws_key={WS_KEY}&limit={start},{limit}"
                products_root = get_xml(products_url)

                if products_root is None:
                    return []

                product_ids = [prod.attrib['id'] for prod in products_root.findall('.//product')]
                return product_ids
            except Exception as e:
                _logger.error(f"Error getting products: {e}")
                return []

        # Start processing
        _logger.info("=== Starting PrestaShop Stock Sync via Products API ===")
        _logger.info(f"Resuming from index: {sync_record.last_processed_index}")

        processed_count = 0
        updated_count = 0
        not_found_in_odoo_count = 0
        error_count = 0

        # Process products in batches
        batch_size = 20  # Small batch size to avoid timeouts
        start_index = sync_record.last_processed_index  # Resume from where we left off

        while True:
            # Check time limit
            if time.time() - start_time > TIME_LIMIT:
                _logger.info(f"Time limit reached. Saving progress at index {start_index}")
                sync_record.last_processed_index = start_index
                break

            # Get batch of product IDs
            product_ids = get_products_with_pagination(start_index, batch_size)

            if not product_ids:
                _logger.info("No more products to process - SYNC COMPLETED!")
                sync_record.last_processed_index = 0  # Reset for next full sync
                break

            _logger.info(f"Processing batch: products {start_index} to {start_index + len(product_ids)}")

            for product_id in product_ids:
                try:
                    # Get product details including EAN13 and stock_availables
                    product_url = f"{BASE_URL}/products/{product_id}?ws_key={WS_KEY}"
                    product_detail = get_xml(product_url)

                    if product_detail is None:
                        error_count += 1
                        continue

                    # Extract EAN13
                    ean13_node = product_detail.find('.//ean13')
                    if ean13_node is None or not ean13_node.text:
                        _logger.info(f"Product {product_id}: No EAN13 found, skipping")
                        processed_count += 1
                        continue

                    ean13 = ean13_node.text.strip()
                    if not ean13:
                        _logger.info(f"Product {product_id}: Empty EAN13, skipping")
                        processed_count += 1
                        continue

                    _logger.info(f"Processing PrestaShop Product {product_id} | EAN13: {ean13}")

                    # Search for this EAN13 in Odoo
                    odoo_product = self.env['product.product'].search([('default_code', '=', ean13)], limit=1)

                    if not odoo_product:
                        _logger.info(f"EAN13 {ean13}: not found in Odoo, skipping")
                        not_found_in_odoo_count += 1
                        processed_count += 1
                        continue

                    odoo_qty = odoo_product.qty_available
                    _logger.info(f"EAN13 {ean13}: found in Odoo with quantity {odoo_qty}")

                    # Get stock_availables from the product XML
                    stock_availables = product_detail.findall('.//associations/stock_availables/stock_available')

                    if not stock_availables:
                        _logger.warning(f"Product {product_id}: No stock_availables found")
                        error_count += 1
                        processed_count += 1
                        continue

                    # Process each stock_available for this product
                    product_updated = False
                    for stock_available_elem in stock_availables:
                        stock_id_node = stock_available_elem.find('id')
                        if stock_id_node is None:
                            continue

                        stock_id = stock_id_node.text
                        _logger.info(f"Updating stock_available ID: {stock_id}")

                        # Get current stock_available details
                        stock_url = f"{BASE_URL}/stock_availables/{stock_id}?ws_key={WS_KEY}"
                        stock_detail = get_xml(stock_url)

                        if stock_detail is None:
                            _logger.warning(f"Failed to get stock_available {stock_id}")
                            continue

                        stock_available_node = stock_detail.find('stock_available')
                        if stock_available_node is None:
                            continue

                        # Update quantity
                        quantity_node = stock_available_node.find('quantity')
                        if quantity_node is not None:
                            old_qty = quantity_node.text
                            quantity_node.text = str(int(odoo_qty))

                            # Prepare update XML
                            updated_doc = ET.Element('prestashop', xmlns_xlink="http://www.w3.org/1999/xlink")
                            updated_doc.append(stock_available_node)
                            updated_data = ET.tostring(updated_doc, encoding='utf-8', xml_declaration=True)

                            # Send update
                            response = put_xml(stock_url, updated_data)

                            if response and response.status_code in (200, 201):
                                _logger.info(
                                    f"✔ Updated stock {stock_id} for EAN13 {ean13}: {old_qty} → {int(odoo_qty)}")
                                product_updated = True
                            else:
                                _logger.warning(f"Failed to update stock {stock_id} for EAN13 {ean13}")

                    if product_updated:
                        updated_count += 1

                    processed_count += 1

                    # Small delay to avoid overwhelming the API
                    time.sleep(0.1)

                except Exception as e:
                    _logger.error(f"Error processing product {product_id}: {e}")
                    error_count += 1
                    processed_count += 1
                    continue

            # Move to next batch
            start_index += batch_size

            # Add delay between batches
            time.sleep(0.5)

        # Final summary
        _logger.info("=== SYNC SUMMARY ===")
        _logger.info(f"Total processed this run: {processed_count}")
        _logger.info(f"Successfully updated: {updated_count}")
        _logger.info(f"Not found in Odoo: {not_found_in_odoo_count}")
        _logger.info(f"Errors: {error_count}")
        _logger.info(f"Next run will start from index: {sync_record.last_processed_index}")
        _logger.info("=== END SYNC ===")

        return True
    @api.model
    def update_prestashop_stock(self):
        """Main method - calls the products API sync"""
        return self.update_prestashop_stock_via_products()