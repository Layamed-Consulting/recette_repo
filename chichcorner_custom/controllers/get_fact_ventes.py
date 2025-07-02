from odoo import http, registry, api
from odoo.http import request
import json
import werkzeug


def validate_api_key(api_key):
    """Validate the API key and return the associated user if valid"""
    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)
    return api_key_record.user_id if api_key_record else None

class DimensionProduitAPI(http.Controller):

    @http.route("/api/dimension_produit", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_produit(self, id_pdt_start=None, id_pdt_end=None, **kwargs):
        try:
            # Extract database, admin, and password from headers
            api_key = request.httprequest.headers.get('Authorization')
            db_name = request.httprequest.headers.get('db')
            admin_user = request.httprequest.headers.get('user')
            admin_password = request.httprequest.headers.get('password')

            # Validate API key
            user = validate_api_key(api_key)
            if not user:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            # Check if the user has admin access
            if not user.has_group('base.group_system'):
                return http.Response(
                    json.dumps({"error": "Access Denied", "details": "This API requires admin access"}),
                    status=403,
                    content_type="application/json"
                )

            # Switch to the specified database
            if db_name and admin_user and admin_password:
                registry(db_name).cursor().close()
                request.session.db = db_name
                request.session.login = admin_user
                request.session.password = admin_password
                request.session.authenticate(db_name, admin_user, admin_password)

            request.update_env(user=user)

            domain = []
            if id_pdt_start and id_pdt_end:
                domain.append(('id', '>=', int(id_pdt_start)))
                domain.append(('id', '<=', int(id_pdt_end)))

            products = request.env['product.template'].sudo().search(domain)

            produit_data = []
            for product in products:
                pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else None

                taxes = [tax.name for tax in product.taxes_id] if product.taxes_id else None

                supplier_info = [
                    {
                        "Nom du fournisseur": supplier.display_name,
                        "Prix": supplier.price,
                        "Devise": supplier.currency_id.name if supplier.currency_id else None
                    }
                    for supplier in product.seller_ids
                ]

                pricelist_item = request.env['product.pricelist.item'].sudo().search([
                    ('product_tmpl_id', '=', product.id),
                    ('pricelist_id.active', '=', True)
                ], limit=1)
                product_price = pricelist_item.fixed_price if pricelist_item else None

                stock_quantities = {}
                stock_records = request.env['stock.quant'].sudo().search([
                    ('product_id', '=', product.product_variant_id.id)
                ])
                for stock in stock_records:
                    location_name = stock.location_id.complete_name
                    stock_quantities[location_name] = stock.quantity

                produit_data.append({
                    "Nom du Produit": product.name,
                    "Code barre": product.barcode,
                    "default code": product.default_code,
                    "Item ID": product.x_studio_item_id,
                    "Coût": product.standard_price,
                    "Prix de vente": product_price,
                    "HS Code": product.x_studio_hs_code,
                    "Collection": product.x_studio_origine_pays,
                    "Composition": product.x_studio_composition,
                    "Type de produit": product.detailed_type,
                    "Politique de fabrication": product.invoice_policy,
                    "Stock selon l'emplacement": stock_quantities,
                    "Catégorie de produit": product.categ_id.name,
                    "Marque du produit": pos_categories,
                    "Disponible en POS": product.available_in_pos,
                    "Taxes": taxes,
                    "Informations fournisseur": supplier_info,
                })

            return request.make_json_response(produit_data, status=200)

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
            error_message = f"Error fetching Dimension_produit: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

class SalesOrderAPI(http.Controller):

    @http.route("/api/pos_orders/<int:id>", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_orders(self, id):
        try:
            api_key = request.httprequest.headers.get('Authorization')

            user = validate_api_key(api_key)
            if not user:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            request.update_env(user=user)

            pos_order = request.env['pos.order'].sudo().search([('id', '=', id)], limit=1)


            if not pos_order:
                return request.make_json_response({
                    "message": "ID not found",
                }, status=400)

            products = []
            for line in pos_order.lines:
                products.append({
                    "Product": line.full_product_name,
                    "price": line.price_unit,
                    "quantity": line.qty
                })

            payments = []
            for payment in pos_order.payment_ids:
                payments.append({
                    "payment_date": payment.payment_date,
                    "payment_method_id": payment.payment_method_id.id,
                    "payment_method_name": payment.payment_method_id.name,
                    "amount": payment.amount
                })

            response_data = {
                "id": pos_order.id,
                "session_id": pos_order.session_id.id,
                "date_order": pos_order.date_order,
                "employee_id": pos_order.employee_id,
                "products": products,
                "payments": payments
            }
            return request.make_json_response(response_data, status=200)

        except Exception as e:
            error_message = f"Error fetching POS orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )