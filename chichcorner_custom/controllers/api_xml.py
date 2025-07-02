from odoo import http
import xmlrpc.client
import json
from odoo.http import request


ODOO_URL = 'http://localhost:8069'
ODOO_DB = 'REAL_DB2'
ODOO_USERNAME = 'admin'

'''
#api for product is done
class ProductAPI(http.Controller):

    @http.route('/api/get_product_details', type='http', auth='none', methods=['GET'], csrf=False)
    def get_product_details(self,id_pdt_start=None, id_pdt_end=None, **kwargs):
        try:
            # Get the API key from the Authorization header
            api_key = request.httprequest.headers.get('Authorization')

            # Check if the API key is provided
            if not api_key:
                return http.Response(
                    json.dumps({'error': 'API key is missing in the request header'}),
                    status=403, content_type='application/json'
                )

            # Use XML-RPC to search for the API key in the correct database
            common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({'error': 'Unauthorized, invalid or inactive API key'}),
                    status=403, content_type='application/json'
                )

            models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

            domain = []
            if id_pdt_start and id_pdt_end:
                domain = [('id', '>=', int(id_pdt_start)), ('id', '<=', int(id_pdt_end))]
            # Fetch product details
            products = models.execute_kw(
                ODOO_DB, uid, api_key, 'product.template', 'search_read',
                [domain],
                {'fields': [
                    'name', 'barcode', 'default_code', 'x_studio_item_id',
                    'standard_price', 'x_studio_hs_code', 'x_studio_origine_pays',
                    'x_studio_composition', 'detailed_type', 'invoice_policy',
                    'available_in_pos'
                ]}
            )

            product_data = []

            # Iterate over products
            for product in products:

                # Fetch supplier information for the product
                suppliers = models.execute_kw(
                    ODOO_DB, uid, api_key, 'product.supplierinfo', 'search_read',
                    [[('product_tmpl_id', '=', product['id'])]],
                    {'fields': ['display_name', 'price', 'currency_id']}
                )

                # Create supplier info list
                supplier_info = [
                    {
                        "Nom du fournisseur": supplier['display_name'] if 'display_name' in supplier and supplier['display_name'] else "not existe",
                        "Prix": supplier['price'] if 'price' in supplier and supplier['price'] else "0",
                        "Devise": supplier['currency_id'][1] if 'currency_id' in supplier and supplier['currency_id'] else ""
                    }
                    for supplier in suppliers
                ]

                # Fetch stock data for the product
                stock_records = models.execute_kw(
                    ODOO_DB, uid, api_key, 'stock.quant', 'search_read',
                    [[('product_id.product_tmpl_id', '=', product['id'])]],
                    {'fields': ['location_id', 'quantity']}
                )

                # Create stock quantities mapping
                stock_quantities = {}
                for stock in stock_records:
                    location_name = stock['location_id'][1] if 'location_id' in stock and stock['location_id'] else "Unknown Location"
                    stock_quantities[location_name] = stock['quantity']

                # Fetch product price from pricelist
                pricelist_items = models.execute_kw(
                    ODOO_DB, uid, api_key, 'product.pricelist.item', 'search_read',
                    [[('product_tmpl_id', '=', product['id'])]],
                    {'fields': ['fixed_price']}
                )

                # Get the price from the pricelist (if exists)
                product_price = pricelist_items[0]['fixed_price'] if pricelist_items else "Price not found"

                # Append product data to the list
                product_data.append({
                    "Nom du Produit": product.get('name') if product.get('name') else "",
                    "Code barre": product.get('barcode') if product.get('barcode') else "existe pas",
                    "default_code": product.get('default_code') if product.get('default_code') else "existe pas",
                    "Item ID": product.get('x_studio_item_id') if product.get('x_studio_item_id') else "existe pas",
                    "Cout": product.get('standard_price') if product.get('standard_price') else "existe pas",
                    "Prix de vente": product_price,  # Added product price from pricelist
                    "HS Code": product.get('x_studio_hs_code') if product.get('x_studio_hs_code') else "existe pas",
                    "Collection": product.get('x_studio_origine_pays') if product.get('x_studio_origine_pays') else "existe pas",
                    "Composition": product.get('x_studio_composition') if product.get('x_studio_composition') else "existe pas",
                    "Type de produit": product.get('detailed_type') if product.get('detailed_type') else "existe pas",
                    "Politique de fabrication": product.get('invoice_policy') if product.get('invoice_policy') else "existe pas",
                    "Disponible en POS": product.get('available_in_pos') if product.get('available_in_pos') else "0",
                    "Stock selon l'emplacement": stock_quantities,
                    "Informations fournisseur": supplier_info,

                })

            # Return the product data as JSON
            return http.Response(json.dumps(product_data, ensure_ascii=False), content_type='application/json')

        except Exception as e:
            return http.Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

#api for sales table is done

class PosOrderAPI(http.Controller):

    @http.route("/api/get_pos_ventes", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_orders(self, id_produit=None, id_magasin=None, id_client=None, id_debut=None, id_fin=None, **kwargs):
        try:
            # Get API Key from Header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            # Authenticate using XML-RPC
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({"error": "Unauthorized, invalid or inactive API key"}),
                    status=403,
                    content_type="application/json"
                )

            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            # Build domain filters
            domain = []
            if id_magasin:
                domain.append(('config_id', '=', int(id_magasin)))
            if id_client:
                domain.append(('partner_id', '=', int(id_client)))
            if id_debut and id_fin:
                domain.append(('date_order', '>=', id_debut))
                domain.append(('date_order', '<=', id_fin))

            # Fetch POS orders
            pos_orders = models.execute_kw(
                ODOO_DB, uid, api_key, 'pos.order', 'search_read',
                [domain],
                {'fields': ['name', 'session_id', 'date_order', 'config_id', 'pos_reference',
                            'partner_id', 'employee_id', 'suggestion']}
            )

            pos_data = []
            for order in pos_orders:
                # Fetch POS order lines
                order_lines = models.execute_kw(
                    ODOO_DB, uid, api_key, 'pos.order.line', 'search_read',
                    [[('order_id', '=', order['id'])]],
                    {'fields': ['product_id', 'qty', 'customer_note', 'discount', 'price_subtotal_incl']}
                )

                products = []
                for line in order_lines:
                    if id_produit and line['product_id'][0] != int(id_produit):
                        continue
                    products.append({
                        "id_produit": line['product_id'][0],
                        "Nom": line['product_id'][1],
                        "Quantité": line['qty'],
                        "Note du client": line['customer_note'] if 'customer_note' in line else "",
                        "discount": line['discount'],
                        "Prix": line['price_subtotal_incl'],
                    })

                if not products:
                    continue

                pos_data.append({
                    "Ref": order['name'],
                    "Session": order['session_id'][1] if order['session_id'] else "None",
                    "Date de commande": order['date_order'],
                    "Nom du Magasin": order['config_id'][1] if order['config_id'] else "None",
                    "Ticket de caisse": order['pos_reference'],
                    "Nom du client": order['partner_id'][1] if order['partner_id'] else "",
                    "Caissier": order['employee_id'][1] if order['employee_id'] else "",
                    "Nom du vendeur": order['suggestion'] if 'suggestion' in order else "",
                    "Produits achetés": products,
                })

            return http.Response(json.dumps(pos_data, ensure_ascii=False), content_type="application/json", status=200)

        except Exception as e:
            error_message = f"Error fetching POS orders: {str(e)}"
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

# api for payment methode

class PosPaymentAPI(http.Controller):

    @http.route("/api/get_pos_payments", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_payments(self, id_order_start=None, id_order_end=None, id_magasin=None, id_client=None, id_produit=None, id_debut=None, id_fin=None, **kwargs):
        try:
            # Get API Key from Header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            # Authenticate using XML-RPC
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({"error": "Unauthorized, invalid or inactive API key"}),
                    status=403,
                    content_type="application/json"
                )

            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            # Build domain filters
            domain = []
            if id_order_start and id_order_end:
                domain.append(('id', '>=', int(id_order_start)))
                domain.append(('id', '<=', int(id_order_end)))
            if id_magasin:
                domain.append(('config_id', '=', int(id_magasin)))
            if id_client:
                domain.append(('partner_id', '=', int(id_client)))
            if id_debut and id_fin:
                domain.append(('date_order', '>=', id_debut))
                domain.append(('date_order', '<=', id_fin))
            if id_produit:
                domain.append(('lines.product_id', '=', int(id_produit)))

            # Fetch POS orders
            pos_orders = models.execute_kw(
                ODOO_DB, uid, api_key, 'pos.order', 'search_read',
                [domain],
                {'fields': ['name', 'session_id', 'date_order', 'config_id', 'pos_reference',
                            'partner_id', 'employee_id', 'suggestion', 'payment_ids']}
            )

            payment_data = []
            for order in pos_orders:
                # Fetch payment details
                payment_methods = {}
                if order['payment_ids']:
                    payments = models.execute_kw(
                        ODOO_DB, uid, api_key, 'pos.payment', 'search_read',
                        [[('id', 'in', order['payment_ids'])]],
                        {'fields': ['payment_method_id', 'amount']}
                    )
                    for payment in payments:
                        payment_methods[payment['payment_method_id'][1]] = payment['amount']

                payment_data.append({
                    "Nom du Magasin": order['config_id'][1] if order['config_id'] else "Non spécifié",
                    "Session": order['session_id'][1] if order['session_id'] else "Non spécifié",
                    "Ticket de caisse": order['pos_reference'],
                    "Caissier": order['employee_id'][1] if order['employee_id'] else "Non spécifié",
                    "Date de commande": order['date_order'],
                    "Vendeur": order['suggestion'] if 'suggestion' in order else "Non spécifié",
                    "Nom du Client": order['partner_id'][1] if order['partner_id'] else "Non spécifié",
                    "Méthodes de paiement": payment_methods
                })

            return http.Response(json.dumps(payment_data, ensure_ascii=False), content_type="application/json", status=200)

        except Exception as e:
            error_message = f"Error fetching POS payments: {str(e)}"
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

#api for purchase

class PurchaseOrderAPI(http.Controller):

    @http.route("/api/get_purchase_orders", auth='none', type='http', methods=['GET'], csrf=False)
    def get_purchase_orders(self, id_fournisseur=None, id_user=None, id_debut=None, id_fin=None, **kwargs):
        try:
            # Get API Key from Header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )


            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({"error": "Unauthorized, invalid or inactive API key"}),
                    status=403,
                    content_type="application/json"
                )

            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            # Build domain filters
            domain = []
            if id_fournisseur:
                domain.append(('partner_id', '=', int(id_fournisseur)))
            if id_user:
                domain.append(('user_id', '=', int(id_user)))
            if id_debut and id_fin:
                domain.append(('date_approve', '>=', id_debut))
                domain.append(('date_approve', '<=', id_fin))

            # Fetch Purchase Orders
            purchase_orders = models.execute_kw(
                ODOO_DB, uid, api_key, 'purchase.order', 'search_read',
                [domain],
                {'fields': ['name', 'date_approve', 'partner_id', 'picking_type_id', 'origin',
                            'x_studio_dd_impot', 'x_studio_num_fact_frs', 'amount_total', 'order_line']}
            )

            purchase_data = []
            for po in purchase_orders:
                # Fetch order lines to get total quantity and received quantity
                total_qty, total_received = 0, 0
                if po['order_line']:
                    order_lines = models.execute_kw(
                        ODOO_DB, uid, api_key, 'purchase.order.line', 'search_read',
                        [[('id', 'in', po['order_line'])]],
                        {'fields': ['product_qty', 'qty_received']}
                    )
                    total_qty = sum(line['product_qty'] for line in order_lines)
                    total_received = sum(line['qty_received'] for line in order_lines)

                purchase_data.append({
                    "Bon De Commande": po['name'],
                    "Date de confirmation": po['date_approve'],
                    "Fournisseur": po['partner_id'][1] if po['partner_id'] else "",
                    "Livrer à": po['picking_type_id'][1] if po['picking_type_id'] else "",
                    "Document D'origine": po['origin'] if po['origin'] else "",
                    "DD Impot": po['x_studio_dd_impot'] if 'x_studio_dd_impot' in po else "",
                    "Num Fact Fournisseur": po['x_studio_num_fact_frs'] if 'x_studio_num_fact_frs' in po else "",
                    "Total": po['amount_total'],
                    "Quantité commandée": total_qty,
                    "Quantité reçue": total_received
                })

            return http.Response(json.dumps(purchase_data, ensure_ascii=False), content_type="application/json", status=200)

        except Exception as e:
            error_message = f"Error fetching purchase orders: {str(e)}"
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

# api for inventory
class InventoryAPI(http.Controller):

    @http.route("/api/get_inventory", auth='none', type='http', methods=['GET'], csrf=False)
    def get_inventory(self, id_debut=None, id_fin=None, **kwargs):
        try:
            # Get API Key from Header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            # Authenticate using XML-RPC
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({"error": "Unauthorized, invalid or inactive API key"}),
                    status=403,
                    content_type="application/json"
                )

            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            # Build domain filters
            domain = []
            if id_debut and id_fin:
                domain.append(('in_date', '>=', id_debut))
                domain.append(('in_date', '<=', id_fin))

            # Fetch Inventory Lines
            inventory_lines = models.execute_kw(
                ODOO_DB, uid, api_key, 'stock.quant', 'search_read',
                [domain],
                {'fields': ['location_id', 'product_id', 'inventory_quantity_auto_apply', 'value']}
            )

            inventory_data = []
            for line in inventory_lines:
                product_id = line['product_id'][0] if line['product_id'] else None
                product_name = line['product_id'][1] if line['product_id'] else ""
                location_name = line['location_id'][1] if line['location_id'] else ""

                # Fetch product details
                product_data = models.execute_kw(
                    ODOO_DB, uid, api_key, 'product.product', 'read',
                    [product_id],
                    {'fields': ['categ_id', 'x_studio_item_id', 'product_tmpl_id']}
                )[0] if product_id else {}

                # Get category hierarchy
                category_path = []
                category_id = product_data.get('categ_id', [None, "Non classé"])[0]
                while category_id:
                    category = models.execute_kw(
                        ODOO_DB, uid, api_key, 'product.category', 'read',
                        [category_id],
                        {'fields': ['name', 'parent_id']}
                    )[0]
                    category_path.insert(0, category['name'])
                    category_id = category['parent_id'][0] if category['parent_id'] else None

                # Get product price
                product_price = None
                if product_data.get('product_tmpl_id'):
                    pricelist_item = models.execute_kw(
                        ODOO_DB, uid, api_key, 'product.pricelist.item', 'search_read',
                        [[('product_tmpl_id', '=', product_data['product_tmpl_id'][0]),
                          ('pricelist_id.active', '=', True)]],
                        {'fields': ['fixed_price'], 'limit': 1}
                    )
                    product_price = pricelist_item[0]['fixed_price'] if pricelist_item else None

                inventory_data.append({
                    "L'emplacement": location_name,
                    "Nom du produit": product_name,
                    "Categorie": " / ".join(category_path) if category_path else "Non classé",
                    "Quantité en stock": line['inventory_quantity_auto_apply'],
                    "Valeur en MAD": line['value'],
                    "Item ID": product_data.get('x_studio_item_id'),
                    "Prix de vente": product_price
                })

            return http.Response(json.dumps(inventory_data, ensure_ascii=False), content_type="application/json", status=200)

        except Exception as e:
            error_message = f"Error fetching inventory data: {str(e)}"
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

#api for valorisation

class StockValuationAPI(http.Controller):

    @http.route("/api/get_stock_valuation", auth='none', type='http', methods=['GET'], csrf=False)
    def get_stock_valuation(self, id_val_start=None, id_debut=None, id_fin=None, id_val_end=None, **kwargs):
        try:
            # Get API Key from Header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            # Authenticate using XML-RPC
            common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, api_key, {})
            if not uid:
                return http.Response(
                    json.dumps({"error": "Unauthorized, invalid or inactive API key"}),
                    status=403,
                    content_type="application/json"
                )

            models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

            # Build domain filters
            domain = []
            if id_debut and id_fin:
                domain.append(('create_date', '>=', id_debut))
                domain.append(('create_date', '<=', id_fin))
            if id_val_start and id_val_end:
                domain.append(('id', '>=', id_val_start))
                domain.append(('id', '<=', id_val_end))

            # Fetch Stock Valuation Records
            valuation_records = models.execute_kw(
                ODOO_DB, uid, api_key, 'stock.valuation.layer', 'search_read',
                [domain],
                {'fields': ['create_date', 'reference', 'product_id', 'quantity', 'remaining_qty', 'value', 'remaining_value']}
            )

            valuation_data = []
            total_value = 0

            for record in valuation_records:
                product_id = record['product_id'][0] if record['product_id'] else None
                product_name = record['product_id'][1] if record['product_id'] else ""

                valuation_data.append({
                    "Date de création": record['create_date'],
                    "Référence": record['reference'],
                    "Nom Produit": product_name,
                    "Quantité": record['quantity'],
                    "Quantité restante": record['remaining_qty'],
                    "Valeur en MAD": record['value'],
                    "Valeur restante en MAD": record['remaining_value'],
                })
                total_value += record['value']

            valuation_data.append({
                "Total Valeur en MAD": total_value
            })

            return http.Response(json.dumps(valuation_data, ensure_ascii=False), content_type="application/json", status=200)

        except Exception as e:
            error_message = f"Error fetching stock valuation data: {str(e)}"
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )
'''

