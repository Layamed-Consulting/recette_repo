import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from odoo import models, api

_logger = logging.getLogger(__name__)


class CustomerFetcher(models.TransientModel):
    _name = 'customer.fetch'
    _description = 'Customer Data Fetcher'

    API_BASE_URL = "https://www.premiumshop.ma/api"
    WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"

    @api.model
    def fetch_customer_data(self):
        _logger.info("Starting order data fetch...")

        orders_url = f"{self.API_BASE_URL}/orders?ws_key={self.WS_KEY}"

        try:
            _logger.info("Making API request to: %s", orders_url)
            response = requests.get(orders_url, timeout=30)

            if response.status_code == 200:
                _logger.info("SUCCESS: API call successful!")

                root = ET.fromstring(response.content)
                orders = root.find('orders')
                if orders is None:
                    _logger.warning("No <orders> element found in response.")
                    return

                order_elements = orders.findall('order')
                _logger.info("Total orders found: %d", len(order_elements))

                for i, order in enumerate(order_elements):
                    order_id = order.get('id')
                    href = order.get('{http://www.w3.org/1999/xlink}href')

                    # Check if order already exists in Odoo
                    if self.env['stock.website.order'].search([('ticket_id', '=', order_id)], limit=1):
                        _logger.info("Skipping existing order ID=%s", order_id)
                        continue

                    _logger.info("New Order %s: ID=%s, URL=%s", i + 1, order_id, href)
                    self._fetch_and_log_order_details(order_id)

            else:
                _logger.error("FAILED: Status %s - %s", response.status_code, response.text)

        except requests.exceptions.Timeout:
            _logger.error("TIMEOUT: API request timed out")

        except requests.exceptions.ConnectionError:
            _logger.error("🔌 CONNECTION ERROR: Unable to reach API")

        except Exception as e:
            _logger.exception("EXCEPTION: %s", str(e))

        _logger.info("Order data fetch completed")

    def _fetch_and_log_order_details(self, order_id):
        order_url = f"{self.API_BASE_URL}/orders/{order_id}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(order_url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                order = tree.find('order')

                customer_elem = order.find('id_customer')
                address_delivery_elem = order.find('id_address_delivery')

                customer_url = customer_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                address_delivery_url = address_delivery_elem.attrib.get('{http://www.w3.org/1999/xlink}href')

                customer_details = self._get_complete_customer_details(customer_url, address_delivery_url)

                # Get or create contact
                email = customer_details.get('email')
                partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': f"{customer_details.get('firstname', '')} {customer_details.get('lastname', '')}".strip(),
                        'email': email,
                        'phone': customer_details.get('phone') or customer_details.get('phone_mobile'),
                        'mobile': customer_details.get('phone_mobile'),
                        'company_name': customer_details.get('company'),
                        'street': customer_details.get('address1'),
                        'street2': customer_details.get('address2'),
                        'city': customer_details.get('city'),
                        'zip': customer_details.get('postcode'),
                        'country_id': self.env['res.country'].search([('name', '=', customer_details.get('country'))], limit=1).id if customer_details.get('country') else False,
                    })
                    _logger.info("Created new partner: %s", partner.name)
                else:
                    _logger.info("Partner already exists: %s", partner.name)

                # Order info
                date_commande_str = order.findtext('date_add', default='').strip()
                date_commande = datetime.strptime(date_commande_str, '%Y-%m-%d %H:%M:%S').date() if date_commande_str else None
                reference = order.findtext('reference', default='').strip()
                payment = order.findtext('payment', default='').strip()
                order_rec = self.env['stock.website.order'].create({
                    'ticket_id': order_id,
                    'reference': reference,
                    'client_name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                    'mobile': partner.mobile,
                    'adresse': partner.street,
                    'second_adresse': partner.street2,
                    'city': partner.city,
                    'postcode': partner.zip,
                    'pays': partner.country_id,
                    'date_commande': date_commande,
                    'payment_method': payment,
                })

                order_rows = order.findall('.//order_row')
                total_amount = 0

                for row in order_rows:
                    product_name = row.findtext('product_name', default='').strip()
                    product_reference = row.findtext('product_reference', default='').strip()
                    quantity = row.findtext('product_quantity', default='0').strip()
                    price = row.findtext('product_price', default='0.00').strip()
                    unit_price_incl = row.findtext('unit_price_tax_incl', default='0.00').strip()
                    line_total = float(quantity) * float(unit_price_incl) if quantity and unit_price_incl else 0
                    total_amount += line_total

                    product = self.env['product.product'].search([('default_code', '=', product_reference)], limit=1)
                    if not product:
                        _logger.warning("No product found with reference: %s", product_reference)
                        continue

                    self.env['stock.website.order.line'].create({
                        'order_id': order_rec.id,
                        'product_id': product.id,
                        'product_name': product.name,
                        'quantity': float(quantity),
                        'discount': float(row.findtext('total_discounts', default='0.00')),
                        'price': float(price),
                    })

                total_paid = order.findtext('total_paid_tax_incl', default='0.00')
                payment_method = order.findtext('payment', default='')

                _logger.info("ORDER #%s Summary:", order_id)
                _logger.info("   Total Paid: %s MAD", total_paid)
                _logger.info("   Payment Method: %s", payment_method)
                _logger.info("=" * 80)

            else:
                _logger.error("Failed to fetch order details for %s, status code: %s", order_id, response.status_code)
        except Exception as e:
            _logger.exception("Exception fetching details for order %s: %s", order_id, str(e))

    def _get_complete_customer_details(self, customer_url, address_url):
        """Fetch complete customer details including address information"""
        customer_details = {}

        # Fetch customer basic info
        if customer_url:
            customer_data = self._fetch_api_data(f"{customer_url}?ws_key={self.WS_KEY}")
            if customer_data:
                tree = ET.fromstring(customer_data)
                customer_details.update({
                    'firstname': self._get_text_content(tree, './/firstname'),
                    'lastname': self._get_text_content(tree, './/lastname'),
                    'email': self._get_text_content(tree, './/email'),
                })

        # Fetch address details
        if address_url:
            address_data = self._fetch_api_data(f"{address_url}?ws_key={self.WS_KEY}")
            if address_data:
                tree = ET.fromstring(address_data)
                customer_details.update({
                    'phone': self._get_text_content(tree, './/phone'),
                    'phone_mobile': self._get_text_content(tree, './/phone_mobile'),
                    'company': self._get_text_content(tree, './/company'),
                    'address1': self._get_text_content(tree, './/address1'),
                    'address2': self._get_text_content(tree, './/address2'),
                    'city': self._get_text_content(tree, './/city'),
                    'postcode': self._get_text_content(tree, './/postcode'),
                })

                # Get country name if available
                country_elem = tree.find('.//id_country')
                if country_elem is not None:
                    country_url = country_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                    if country_url:
                        country_data = self._fetch_api_data(f"{country_url}?ws_key={self.WS_KEY}")
                        if country_data:
                            country_tree = ET.fromstring(country_data)
                            country_name = self._get_text_content(country_tree, './/name')
                            customer_details['country'] = country_name

        return customer_details

    def _fetch_api_data(self, url):
        """Helper method to fetch data from API"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                _logger.warning("Failed to fetch data from %s (status %s)", url, response.status_code)
                return None
        except Exception as e:
            _logger.exception("Exception fetching data from %s: %s", url, str(e))
            return None

    def _get_text_content(self, tree, xpath):
        """Helper method to safely extract text content from XML"""
        element = tree.find(xpath)
        return element.text.strip() if element is not None and element.text else ''

    def _get_customer_name(self, customer_url):
        """Legacy method - kept for compatibility"""
        if not customer_url:
            return "Unknown"

        url = f"{customer_url}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                firstname = tree.find('.//firstname')
                lastname = tree.find('.//lastname')
                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                return f"{firstname_text} {lastname_text}".strip()
            else:
                _logger.warning("Failed to fetch customer data at %s (status %s)", url, response.status_code)
                return "Unknown"
        except Exception as e:
            _logger.exception("Exception fetching customer data from %s: %s", url, str(e))
            return "Unknown"