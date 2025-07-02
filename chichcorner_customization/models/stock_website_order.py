from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import xml.etree.ElementTree as ET
_logger = logging.getLogger(__name__)

class WebsiteOrder(models.Model):
    _name = 'stock.website.order'
    _description = 'Stock Website Order Synced from API'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ticket_id = fields.Char(string="Id Commande", required=True, unique=True)
    reference = fields.Char(string="Référence de la commande")
    payment_method = fields.Char(string="Mode de Paiement")
    store_id = fields.Integer(string="Store ID")
    client_name = fields.Char(string="Nom du Client")
    date_commande = fields.Date(string="Date de Commande")
    line_ids = fields.One2many('stock.website.order.line', 'order_id', string="Lignes de Commande")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    adresse = fields.Char(string="Adresse 1")
    second_adresse = fields.Char(string="Adresse 2")
    city = fields.Char(string="Ville")
    postcode = fields.Char(string="Postcode")
    pays= fields.Char(string="Pays")
    status = fields.Selection([
        ('initial', 'Initial'),
        ('prepare', 'Préparé'),
        ('delivered', 'Livré'),
        ('en_cours_preparation', 'En cours de préparation'),
        ('encourdelivraison', 'En cours de Livraison'),
    ], string="Statut", default='initial')
    pos_order_id = fields.Many2one('pos.order', string="POS Order")

    '''
    def action_send_to_pos(self):
        for order in self:
            if not order.line_ids:
                raise UserError("Cette commande n'a pas de lignes de commande.")
            if order.pos_order_id:
                raise UserError("Cette commande a déjà été traité.")

            self._update_order_lines_with_warehouse_info(order)
            # Group lines by warehouse/stock location
            warehouse_groups = self._group_lines_by_warehouse(order)

            if not warehouse_groups:
                raise UserError("Aucun produit en stock trouvé pour cette commande.")

            created_pos_orders = []

            # Create separate POS orders for each warehouse
            for warehouse, lines_data in warehouse_groups.items():
                try:
                    pos_order = self._create_pos_order_for_warehouse(order, warehouse, lines_data)
                    created_pos_orders.append(pos_order)
                except Exception as e:
                    # If there's an error, clean up already created orders
                    for created_order in created_pos_orders:
                        created_order.unlink()
                    raise UserError(f"Erreur lors de la création de la commande POS pour {warehouse.name}: {str(e)}")

            # Update order status and link to the first POS order (or you could link to all)
            order.status = 'en_cours_preparation'
            if created_pos_orders:
                order.pos_order_id = created_pos_orders[0].id

            # Create success message with details of all created orders
            message_parts = []
            for pos_order in created_pos_orders:
                warehouse_name = pos_order.config_id.name
                message_parts.append(f"- {warehouse_name}")

            success_message = f"Commande {order.ticket_id} divisée et envoyée vers {len(created_pos_orders)} POS:\n" + "\n".join(
                message_parts)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Succès',
                    'message': success_message,
                    'type': 'success',
                }
            }
'''
    API_BASE_URL = "https://www.premiumshop.ma/api"
    WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"
    '''added'''
    @api.model
    def sync_status_to_prestashop(self):
        """
        Cron job to sync Odoo order status to PrestaShop.
        Updates these Odoo statuses:
        - 'en_cours_preparation' => PrestaShop status ID 11
        - 'prepare'              => PrestaShop status ID 9
        - 'encourdelivraison'    => PrestaShop status ID 4
        - 'delivered'            => PrestaShop status ID 5
        """
        _logger.info("Starting PrestaShop status synchronization...")

        # Sync only the supported statuses
        orders_to_sync = self.search([
            ('status', 'in', ['en_cours_preparation', 'prepare', 'encourdelivraison', 'delivered']),
            ('reference', '!=', False),
        ])

        _logger.info(f"Found {len(orders_to_sync)} orders to sync")

        synced_count = 0
        error_count = 0

        for order in orders_to_sync:
            try:
                if self._update_prestashop_order_status(order):
                    synced_count += 1
                    _logger.info(f"Successfully synced order {order.reference} with status {order.status}")
                else:
                    error_count += 1
                    _logger.error(f"Failed to sync order {order.reference}")
            except Exception as e:
                error_count += 1
                _logger.error(f"Error syncing order {order.reference}: {str(e)}")

        _logger.info(f"Sync completed. Synced: {synced_count}, Errors: {error_count}")
        return {
            'synced': synced_count,
            'errors': error_count,
            'total': len(orders_to_sync)
        }

    def _find_prestashop_order_by_reference(self, reference):
        """
        Find PrestaShop order ID by reference using basic authentication
        """
        try:
            url = f"{self.API_BASE_URL}/orders"
            params = {
                'filter[reference]': reference,
            }

            response = requests.get(url, auth=(self.WS_KEY, ''), params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            order_elem = root.find('.//order')

            if order_elem is not None and 'id' in order_elem.attrib:
                order_id = order_elem.attrib['id']
                _logger.info(f"Found PrestaShop order ID {order_id} for reference {reference}")
                return order_id
            else:
                _logger.warning(f"No order found in PrestaShop with reference {reference}")
                return None

        except requests.exceptions.RequestException as e:
            _logger.error(f"HTTP error while searching for order: {str(e)}")
            return None
        except ET.ParseError as e:
            _logger.error(f"XML parsing error: {str(e)}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error while searching for order: {str(e)}")
            return None

    def _update_prestashop_order_status(self, order):
        """
        Update PrestaShop order status based on Odoo order status
        """
        try:
            prestashop_order_id = self._find_prestashop_order_by_reference(order.reference)

            if not prestashop_order_id:
                _logger.warning(f"Order with reference '{order.reference}' not found in PrestaShop")
                return False

            # Mapping Odoo status to PrestaShop current_state ID
            status_mapping = {
                'en_cours_preparation': 11,
                'prepare': 9,
                'encourdelivraison': 4,
                'delivered': 5,
            }

            prestashop_status_id = status_mapping.get(order.status)

            if not prestashop_status_id:
                _logger.warning(f"No PrestaShop status mapping for Odoo status '{order.status}'")
                return False

            return self._update_prestashop_order_status_by_id(prestashop_order_id, prestashop_status_id)

        except Exception as e:
            _logger.error(f"Error updating PrestaShop order status: {str(e)}")
            return False

    def _update_prestashop_order_status_by_id(self, order_id, status_id):
        """
        Update the current_state of a PrestaShop order
        """
        try:
            url = f"{self.API_BASE_URL}/orders/{order_id}"
            response = requests.get(url, auth=(self.WS_KEY, ''))
            response.raise_for_status()

            root = ET.fromstring(response.content)

            current_state = root.find('.//current_state')
            if current_state is not None:
                current_state.text = str(status_id)
            else:
                _logger.error(f"Could not find current_state field in order {order_id}")
                return False

            xml_data = ET.tostring(root, encoding='utf-8', method='xml')

            headers = {'Content-Type': 'application/xml'}

            update_response = requests.put(
                url,
                auth=(self.WS_KEY, ''),
                data=xml_data,
                headers=headers
            )
            update_response.raise_for_status()

            _logger.info(f"Successfully updated PrestaShop order {order_id} to status {status_id}")
            return True

        except requests.exceptions.RequestException as e:
            _logger.error(f"HTTP error while updating order status: {str(e)}")
            return False
        except ET.ParseError as e:
            _logger.error(f"XML parsing error: {str(e)}")
            return False
        except Exception as e:
            _logger.error(f"Unexpected error while updating order status: {str(e)}")
            return False

    '''added'''
    @api.model
    def auto_process_initial_orders(self):

        try:
            # Find all orders with 'initial' status
            initial_orders = self.search([('status', '=', 'initial')])

            processed_count = 0
            failed_count = 0

            for order in initial_orders:
                try:
                    # Check if any products have stock_count = 0
                    out_of_stock_products = []
                    for line in order.line_ids:
                        if line.stock_count == 0:
                            product_name = line.product_name or (
                                line.product_id.name if line.product_id else 'Produit inconnu')
                            out_of_stock_products.append(product_name)

                    # Call the action_send_to_pos method
                    result = order.action_send_to_pos()

                    # Add chatter message based on stock situation
                    if out_of_stock_products:
                        stock_message = f"Traitement le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}: "
                        stock_message += f"Produits sans stock:\n"
                        for product in out_of_stock_products:
                            stock_message += f"- {product} n'existe pas en stock\n"

                        order.message_post(
                            body=stock_message,
                            subject="Traitement- Rupture de Stock"
                        )
                    else:
                        order.message_post(
                            body=f"Commande traitée le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}",
                            subject="Traitement Automatique"
                        )

                    _logger.info(f"Auto-processed order {order.ticket_id}")
                    processed_count += 1

                except Exception as e:
                    # Log the error but continue with other orders
                    _logger.error(f"Failed to auto-process order {order.ticket_id}: {str(e)}")
                    failed_count += 1

                    # Add error note to the order's chatter
                    order.message_post(
                        body=f"Échec du traitement automatique le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}: {str(e)}",
                        subject="Erreur Traitement Automatique"
                    )

            # Log summary
            _logger.info(f"Auto-processing completed: {processed_count} orders processed, {failed_count} orders failed")

            return {
                'processed': processed_count,
                'failed': failed_count,
                'total': len(initial_orders)
            }

        except Exception as e:
            _logger.error(f"Error in auto_process_initial_orders: {str(e)}")
            return {'error': str(e)}

    def action_send_to_pos(self):
        for order in self:
            if not order.line_ids:
                raise UserError("Cette commande n'a pas de lignes de commande.")
            if order.pos_order_id:
                raise UserError("Cette commande a déjà été traité.")

            # Separate in-stock and out-of-stock lines
            in_stock_lines, out_of_stock_lines = self._separate_lines_by_stock(order)

            # Update out-of-stock lines status to 'annuler'
            for line in out_of_stock_lines:
                line.write({'status_ligne_commande': 'annuler'})

            # If no products are in stock, update order status and show message
            if not in_stock_lines:
                order.status = 'initial'  # or whatever status you prefer
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': f'Commande {order.ticket_id}: Aucun produit en stock. Tous les produits ont été annulés.',
                        'type': 'warning',
                    }
                }

            # Process only in-stock lines
            self._update_order_lines_with_warehouse_info_selective(order, in_stock_lines)

            # Group in-stock lines by warehouse
            warehouse_groups = self._group_lines_by_warehouse_selective(in_stock_lines)

            created_pos_orders = []

            # Create separate POS orders for each warehouse
            for warehouse, lines_data in warehouse_groups.items():
                try:
                    pos_order = self._create_pos_order_for_warehouse(order, warehouse, lines_data)
                    created_pos_orders.append(pos_order)

                    # Update in-stock lines status to 'en_cours_preparation'
                    for line in lines_data:
                        line.write({'status_ligne_commande': 'en_cours_preparation'})

                except Exception as e:
                    # If there's an error, clean up already created orders
                    for created_order in created_pos_orders:
                        created_order.unlink()
                    raise UserError(f"Erreur lors de la création de la commande POS pour {warehouse.name}: {str(e)}")

            # Update order status and link to the first POS order
            order.status = 'en_cours_preparation'
            if created_pos_orders:
                order.pos_order_id = created_pos_orders[0].id

            # Show warning notification if some products are out of stock
            if out_of_stock_lines:
                out_of_stock_products = []
                for line in out_of_stock_lines:
                    product_name = line.product_name or (line.product_id.name if line.product_id else 'Produit inconnu')
                    out_of_stock_products.append(f"- {product_name}")

                warning_message = f"Attention! Produit(s) à quantité 0 en stock:\n"
                warning_message += "\n".join(out_of_stock_products)
                warning_message += f"\n\nMais la commande {order.ticket_id} a été traitée pour les autres produits disponibles."

                # Return warning notification first
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention - Rupture de stock',
                        'message': warning_message,
                        'type': 'warning',
                        'sticky': True  # Make it stay visible longer
                    }
                }

            # If all products were in stock, show success message
            else:
                # Create success message with details
                message_parts = []
                for pos_order in created_pos_orders:
                    warehouse_name = pos_order.config_id.name
                    message_parts.append(f"- {warehouse_name}")

                success_message = f"Commande {order.ticket_id} traitée avec succès!\n"
                success_message += f"Tous les produits envoyés vers {len(created_pos_orders)} POS:\n"
                success_message += "\n".join(message_parts)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Succès',
                        'message': success_message,
                        'type': 'success',
                    }
                }

    def action_check_pos_status(self):
        """Manual action to check and update order status based on POS order state"""
        for order in self:
            order._check_and_update_status()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Vérification terminée',
                'message': 'Statut des commandes vérifié et mis à jour si nécessaire.',
                'type': 'info',
            }
        }
    @api.model
    def _cron_check_pos_orders_status(self):
        """Cron job to automatically check and update order status"""
        orders_to_check = self.search([
            ('status', '=', 'en_cours_preparation')
        ])

        for order in orders_to_check:
            order._check_and_update_status()
    def _separate_lines_by_stock(self, order):
        """Separate order lines into in-stock and out-of-stock lists"""
        in_stock_lines = []
        out_of_stock_lines = []

        for line in order.line_ids:
            if not line.product_id:
                out_of_stock_lines.append(line)
                continue

            if not line.quantity or line.quantity <= 0:
                out_of_stock_lines.append(line)
                continue

            if not line.price or line.price < 0:
                out_of_stock_lines.append(line)
                continue

            # Check if product has stock
            warehouse = self._find_warehouse_for_product(line.product_id)
            if warehouse:
                in_stock_lines.append(line)
            else:
                out_of_stock_lines.append(line)

        return in_stock_lines, out_of_stock_lines

    def _group_lines_by_warehouse_selective(self, lines):
        """Group given lines by their warehouse based on product stock location"""
        warehouse_groups = {}

        for line in lines:
            # Find warehouse for this product based on stock
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:  # We already filtered for in-stock items, so this should always be true
                # Group lines by warehouse
                if warehouse not in warehouse_groups:
                    warehouse_groups[warehouse] = []
                warehouse_groups[warehouse].append(line)

        return warehouse_groups

    def _update_order_lines_with_warehouse_info_selective(self, order, lines):
        """Update only the given lines with warehouse information and colis numbers"""
        warehouse_to_colis = {}  # Map warehouse to colis number
        colis_counter = 1

        for line in lines:
            if not line.product_id:
                continue

            # Find warehouse for this product
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:
                # Assign colis number based on warehouse
                if warehouse.id not in warehouse_to_colis:
                    warehouse_to_colis[warehouse.id] = colis_counter
                    colis_counter += 1

                # Update the order line with warehouse info
                line.write({
                    'magasin_name': warehouse.name,
                    'numero_colis': warehouse_to_colis[warehouse.id],
                    # 'code_barre': line.product_id.barcode or line.product_id.default_code or '',
                })

    def _check_and_update_status(self):
        """Check if all related POS orders are paid and update status accordingly"""
        if self.status != 'en_cours_preparation':
            return

        # Get all pos_reference values from order lines
        pos_references = self.line_ids.mapped('numero_recu')
        pos_references = [ref for ref in pos_references if ref]  # Remove empty values

        if not pos_references:
            _logger.warning(f"No POS references found for order {self.ticket_id}")
            return

        # Check if all POS orders with these references are paid
        all_paid = True
        for pos_reference in pos_references:
            pos_orders = self.env['pos.order'].search([
                ('pos_reference', '=', pos_reference)
            ])

            if not pos_orders:
                _logger.warning(f"No POS order found with reference {pos_reference}")
                all_paid = False
                break

            # Check if any of the POS orders with this reference is not paid
            unpaid_orders = pos_orders.filtered(lambda o: o.state not in ['paid', 'done', 'invoiced'])
            if unpaid_orders:
                all_paid = False
                break

        # Update status if all related POS orders are paid
        if all_paid:
            self.status = 'prepare'
            _logger.info(f"Order {self.ticket_id} status updated to 'prepare' - all POS orders are paid")
    def _group_lines_by_warehouse(self, order):
        """Group order lines by their warehouse based on product stock location"""
        warehouse_groups = {}

        for line in order.line_ids:
            if not line.product_id:
                raise UserError(f"Produit manquant ou invalide dans la ligne: {line.product_name or 'Unknown'}")

            if not line.quantity or line.quantity <= 0:
                raise UserError(f"Quantité invalide pour le produit '{line.product_id.name}': {line.quantity}")

            if not line.price or line.price < 0:
                raise UserError(f"Prix invalide pour le produit '{line.product_id.name}': {line.price}")

            # Find warehouse for this product based on stock
            warehouse = self._find_warehouse_for_product(line.product_id)

            if not warehouse:
                raise UserError(
                    f"Aucun stock disponible trouvé pour le produit '{line.product_id.name}' dans tous les entrepôts.")

            # Group lines by warehouse
            if warehouse not in warehouse_groups:
                warehouse_groups[warehouse] = []

            warehouse_groups[warehouse].append(line)

        return warehouse_groups

    def _update_order_lines_with_warehouse_info(self, order):
        """Update order lines with warehouse information and colis numbers"""
        warehouse_to_colis = {}  # Map warehouse to colis number
        colis_counter = 1

        for line in order.line_ids:
            if not line.product_id:
                continue

            # Find warehouse for this product
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:
                # Assign colis number based on warehouse
                if warehouse.id not in warehouse_to_colis:
                    warehouse_to_colis[warehouse.id] = colis_counter
                    colis_counter += 1

                # Update the order line with warehouse info
                line.write({
                    'magasin_name': warehouse.name,
                    'numero_colis': warehouse_to_colis[warehouse.id],
                    #'code_barre': line.product_id.barcode or line.product_id.default_code or '',
                })
    def _find_warehouse_for_product(self, product):
        """Find the warehouse that has stock for the given product"""
        # Search for stock quants with available quantity
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal')
        ])

        if not quants:
            return None

        # Find warehouse for the first available quant

        for quant in quants:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', '=', quant.location_id.id)
            ], limit=1)

            if warehouse:
                return warehouse

        return None
    def _create_pos_order_for_warehouse(self, order, warehouse, lines):
        """Create a POS order for a specific warehouse with given lines"""

        # Find POS config for this warehouse
        pos_config = self.env['pos.config'].search([
            ('name', '=', warehouse.name)
        ], limit=1)

        if not pos_config:
            pos_config = self.env['pos.config'].search([
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        if not pos_config:
            raise UserError(f"Aucune configuration POS trouvée pour l'entrepôt '{warehouse.name}'.")

        # Find open session for this POS config
        session = self.env['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state', '=', 'opened')
        ], limit=1)

        if not session:
            raise UserError(
                f"Aucune session POS ouverte pour le point de vente '{pos_config.name}'. Veuillez ouvrir une session POS d'abord.")

        # Prepare order lines for this warehouse
        order_lines = []
        total_amount = 0.0
        tax_amount = 0.0

        for line in lines:
            discount_amount = (line.discount or 0.0) / 100.0
            price_unit = float(line.price)
            qty = float(line.quantity)
            taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == self.env.company)
            tax_rate = taxes[0].amount / 100.0 if taxes else 0.20

            line_total = qty * price_unit * (1 - discount_amount)
            subtotal_incl = line_total
            subtotal_excl = subtotal_incl / (1 + tax_rate)

            total_amount += line_total
            tax_amount += line_total - (line_total / 1.20)

            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'full_product_name': line.product_id.display_name,
                'qty': qty,
                'price_unit': price_unit,
                'discount': line.discount or 0.0,
                'price_subtotal': subtotal_excl,
                'price_subtotal_incl': subtotal_incl,
                'tax_ids': [(6, 0, taxes.ids)] if taxes else False,
            }))

        if not order_lines:
            raise UserError("Aucune ligne de commande valide trouvée pour cet entrepôt.")

        # Find or create partner
        partner = self._find_or_create_partner(order)

        # Find employee
        employee = self.env['hr.employee'].search([('name', '=', 'SBIHI SALMA')], limit=1)
        if not employee:
            raise UserError("Employee not found.")

        # Generate sequence and reference
        #sequence = self._generate_pos_sequence(pos_config, session)
        pos_reference = self._generate_pos_reference(order, warehouse.name)

        pos_user = session.user_id or self.env.user

        pos_order_vals = {
            #'name': sequence,
            'state': 'draft',
            'partner_id': partner.id if partner else False,
            'lines': order_lines,
            'amount_total': float(total_amount),
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'amount_tax': float(tax_amount),
            'config_id': pos_config.id,
            'session_id': session.id,
            'employee_id': employee.id,
            'company_id': session.config_id.company_id.id,
            'pricelist_id': session.config_id.pricelist_id.id if session.config_id.pricelist_id else self.env.company.currency_id.id,
            'fiscal_position_id': partner.property_account_position_id.id if partner and partner.property_account_position_id else False,
            'note': f"Commande importée du site web - Ticket: {order.ticket_id} - Entrepôt: {warehouse.name} - Cashier: {pos_user.name}",
            'date_order': order.date_commande or fields.Datetime.now(),
            'pos_reference': pos_reference,
        }

        pos_order = self.env['pos.order'].create(pos_order_vals)
        for line in lines:
            line.write({
                'numero_recu': pos_reference,
            })
        return pos_order

    def _generate_pos_reference(self, order, warehouse_name=None):
        """
        Generate a POS reference with a UID that matches the expected 14-character format
        The format should be: YYYY-MM-DD-HHH where HHH is a 3-digit counter
        """
        # Try to use the existing reference if it already has the right format
        if order.reference:
            import re
            if re.match(r'^.+[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}$', order.reference):
                base_reference = order.reference
            else:
                base_reference = order.reference
        else:
            base_reference = order.ticket_id or "WEB"

        # Generate a new reference with proper UID format
        current_time = fields.Datetime.now()
        date_part = current_time.strftime('%Y-%m-%d')

        # Generate a 3-digit sequence number based on milliseconds or random
        import random
        sequence_num = str(random.randint(100, 999))

        # Create the UID in the expected format: YYYY-MM-DD-NNN (14 characters including dashes)
        uid = f"{date_part}-{sequence_num}"

        # Include warehouse name in reference if provided
        if warehouse_name:
            return f"WEB-{base_reference}-{warehouse_name}-{uid}"
        else:
            return f"{base_reference}-{uid}"
    def _update_order_lines_with_receipt_number(self, lines, order, warehouse_name):
        """Update order lines with receipt number using the generated POS reference"""
        receipt_number = self._generate_pos_reference(order, warehouse_name)

        for line in lines:
            line.write({
                'numero_recu': receipt_number,
            })
    def _find_or_create_partner(self, order):
        partner = None
        if order.email:
            partner = self.env['res.partner'].search([
                ('email', '=', order.email)
            ], limit=1)

        if not partner and order.client_name:
            partner = self.env['res.partner'].search([
                ('name', '=', order.client_name)
            ], limit=1)

        if not partner:
            partner_vals = {
                'name': order.client_name or 'Client Web',
                'email': order.email or False,
                'phone': order.phone or False,
                'mobile': order.mobile or False,
                'street': order.adresse or False,
                'street2': order.second_adresse or False,
                'city': order.city or False,
                'zip': order.postcode or False,
                'is_company': False,
                'customer_rank': 1,
                'supplier_rank': 0,
            }
            if order.pays:
                country = self.env['res.country'].search([
                    '|',
                    ('name', 'ilike', order.pays),
                    ('code', '=', order.pays)
                ], limit=1)
                if country:
                    partner_vals['country_id'] = country.id

            partner = self.env['res.partner'].create(partner_vals)

        return partner
    '''
    def _generate_pos_sequence(self, pos_config, session):
        return self.env['ir.sequence'].next_by_code('pos.order') or '/'
        '''

class StockWebsiteOrderLine(models.Model):
    _name = 'stock.website.order.line'
    _description = 'Ligne de commande du site'

    order_id = fields.Many2one('stock.website.order', string="Commande")
    product_id = fields.Many2one('product.product', string="Produit")
    product_name = fields.Char(string="Nom du Produit")
    quantity = fields.Float(string="Quantité")
    price = fields.Float(string="Prix", compute="_compute_price_from_pricelist", store=True)
    discount = fields.Float(string="Remise")
    magasin_name = fields.Char(string="Magasin", compute="_compute_magasin_and_stock", store=True,
                               help="Nom du magasin où le produit est stocké")
    stock_count = fields.Float(string="Stock Disponible", compute="_compute_magasin_and_stock", store=True,
                               help="Quantité disponible en stock dans l'entrepôt")
    numero_colis = fields.Integer(string="Numéro Colis", help="Numéro de colis basé sur l'entrepôt de stock")
    code_barre = fields.Char(string="Code Barre", help="Code barre du produit")
    numero_recu = fields.Char(string="Numéro De Ticket", help="Numéro de reçu/ticket de la commande POS")
    status_ligne_commande = fields.Selection([
        ('initial', 'Initial'),
        ('prepare', 'Préparé'),
        ('delivered', 'Livré'),
        ('en_cours_preparation', 'En cours de préparation'),
        ('encourdelivraison', 'En cours de Livraison'),
        ('annuler', 'annuler')
    ], string="Statut", default='initial')
    #payment = fields.Char(string="Mode de paiment")

    @api.depends('product_id')
    def _compute_price_from_pricelist(self):
        """Compute price from product pricelist based on barcode"""
        for line in self:
            if line.product_id:
                # Search for pricelist item by product barcode
                pricelist_item = self.env['product.pricelist.item'].search([
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if pricelist_item:
                    # Use the fixed price from pricelist
                    line.price = pricelist_item.fixed_price
                else:
                    # Fallback to product list price if not found in pricelist
                    line.price = line.product_id.list_price
            else:
                line.price = 0.0
    @api.depends('product_id')
    def _compute_magasin_and_stock(self):
        """Compute warehouse name and stock count for each product"""
        for line in self:
            if line.product_id:
                warehouse, stock_qty = line._get_warehouse_and_stock_for_product(line.product_id)
                line.magasin_name = warehouse.name if warehouse else "Aucun stock"
                line.stock_count = stock_qty
            else:
                line.magasin_name = ""
                line.stock_count = 0.0

    def action_refresh_stock(self):
        """Manual action to refresh stock information"""
        for line in self:
            if line.product_id:
                warehouse, stock_qty = line._get_warehouse_and_stock_for_product(line.product_id)
                line.magasin_name = warehouse.name if warehouse else "Aucun stock"
                line.stock_count = stock_qty
        return True

    @api.depends('product_id')
    def _compute_code_barre(self):
        """Compute barcode for each product"""
        for line in self:
            if line.product_id:
                line.code_barre = line.product_id.default_code or line.product_id.barcode or ''
            else:
                line.code_barre = ''

    def _get_warehouse_and_stock_for_product(self, product):
        """Find the warehouse that has the most stock for the given product and return stock quantity"""
        # Search for stock quants with available quantity
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal')
        ])

        if not quants:
            return None, 0.0

        # Find warehouse with the highest stock quantity
        best_warehouse = None
        best_stock_qty = 0.0

        # Group quants by warehouse and sum quantities
        warehouse_stock = {}

        for quant in quants:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', '=', quant.location_id.id)
            ], limit=1)

            if warehouse:
                if warehouse.id not in warehouse_stock:
                    warehouse_stock[warehouse.id] = {
                        'warehouse': warehouse,
                        'total_qty': 0.0
                    }
                warehouse_stock[warehouse.id]['total_qty'] += quant.quantity

        # Find warehouse with stock
        for warehouse_data in warehouse_stock.values():
            if warehouse_data['total_qty'] > best_stock_qty:
                best_warehouse = warehouse_data['warehouse']
                best_stock_qty = warehouse_data['total_qty']

        return best_warehouse, best_stock_qty

    '''added'''

    @api.model
    def cron_update_stock_disponible(self):
        """
        Simple cron job to update stock disponible for all order lines
        """
        _logger.info("Starting stock update cron...")

        # Get all order lines with barcode
        order_lines = self.search([
            ('code_barre', '!=', False),
            ('code_barre', '!=', '')
        ])

        updated_count = 0

        for line in order_lines:
            try:
                # Find product by barcode
                product = self.env['product.product'].search([
                    ('default_code', '=', line.code_barre)
                ], limit=1)

                if product:
                    # Get stock quantity
                    stock_qty = self._get_stock_quantity(product)

                    # Update stock count
                    line.stock_count = stock_qty
                    updated_count += 1

            except Exception as e:
                _logger.error("Error updating stock for line %d: %s", line.id, str(e))
                continue

        _logger.info("Stock update completed: %d lines updated", updated_count)

    def _get_stock_quantity(self, product):
        """Get total available stock for product"""
        stock_quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal')
        ])

        total_qty = sum(quant.quantity for quant in stock_quants)
        return total_qty
