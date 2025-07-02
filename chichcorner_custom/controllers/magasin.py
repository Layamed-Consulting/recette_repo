from odoo import http, fields, models,api
from odoo.http import request
from odoo.api import SUPERUSER_ID
import json
import odoo
import werkzeug.exceptions

class APIKey(models.Model):
    _name = 'api.key'
    _description = 'API Keys'

    name = fields.Char('Key Name', required=True)
    key = fields.Char('API Key', required=True)
    active = fields.Boolean('Active', default=True)
    user_id = fields.Many2one('res.users', string='Associated User', required=True)
    db_name = fields.Char('Database', required=True)



class ProductAPI(http.Controller):

    @http.route('/api/new_products', type="http", auth="none", methods=['GET'], csrf=False)
    def get_products(self, **kwargs):
        """
        API to authenticate user and fetch product details from the specified database.
        Request Headers:
        - 'db': Database name
        - 'login': Username
        - 'password': User's password
        """
        # Extract headers
        db = request.httprequest.headers.get('db')
        username = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')

        if not db or not username or not password:
            return http.Response(
                json.dumps({"error": "Missing credentials", "details": "Provide 'db', 'login', and 'password' in headers."}),
                status=400,
                content_type="application/json"
            )

        try:
            # Authenticate the user in the specified database
            request.session.db = db
            uid = request.session.authenticate(db, username, password)

            if not uid:
                return http.Response(
                    json.dumps({"error": "Authentication failed", "details": "Invalid credentials."}),
                    status=401,
                    content_type="application/json"
                )

            # Get product details
            products = request.env['product.template'].sudo().search([])

            product_data = []
            for product in products:
                pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else None
                product_data.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "product_type": product.type,
                    "sales_price": product.list_price,
                    "cost": product.standard_price,
                    "barcode": product.barcode,
                    "default_code": product.default_code,
                    "product_category": product.categ_id.name,
                    "pos_category": pos_categories,
                    "available_in_pos": product.available_in_pos
                })

            return http.Response(json.dumps(product_data), status=200, content_type="application/json")

        except werkzeug.exceptions.Unauthorized as e:
            return http.Response(
                json.dumps({"error": "Authentication Required", "details": str(e)}),
                status=401,
                content_type="application/json"
            )
        except werkzeug.exceptions.Forbidden as e:
            return http.Response(
                json.dumps({"error": "Access Denied", "details": str(e)}),
                status=403,
                content_type="application/json"
            )
        except Exception as e:
            error_message = f"Error fetching products: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

'''
def validate_api_key(api_key):
    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)

    return api_key_record.user_id if api_key_record else None

class DimensionMagasinAPI(http.Controller):

    @http.route("/api/<string:db>/dimension_magasin", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_magasin(self, db, **kwargs):
        try:

            if db not in http.db_list():
                return http.Response(
                    json.dumps({"error": "Invalid database"}),
                    status=400,
                    content_type="application/json"
                )


            registry = odoo.modules.registry.Registry(db)

            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})

                # Validate API key
                user = validate_api_key(api_key)
                if not user:
                    return http.Response(
                        json.dumps({"error": "Invalid API key"}),
                        status=401,
                        content_type="application/json"
                    )

                # Use the environment with the specific database
                magasins = env['pos.config'].sudo().search([])
                magasin_data = []

                for magasin in magasins:
                    basic_employees = magasin.basic_employee_ids
                    advanced_employees = magasin.advanced_employee_ids

                    magasin_data.append({
                        "magasin_id": magasin.id,
                        "nom": magasin.name,
                        "employes_de_base": [employee.name for employee in basic_employees],
                        "employes_avances": [employee.name for employee in advanced_employees],
                    })

                return http.Response(
                    json.dumps(magasin_data),
                    status=200,
                    content_type="application/json"
                )

        except Exception as e:
            error_message = f"Error fetching Dimension_magasin: {str(e)}"
            if 'cr' in locals():
                cr.rollback()
            return http.Response(
                json.dumps({"error": "anass error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

'''

