from odoo import models, fields, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class WebsiteOrder(models.Model):
    _name = 'stock.website.order'
    _description = 'Stock Website Order Synced from API'

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
        ('delivered', 'Livré')
    ], string="Statut", default='initial')
    pos_order_id = fields.Many2one('pos.order', string="POS Order")

    def action_send_to_pos(self):
        for order in self:
            if not order.line_ids:
                raise UserError("Cette commande n'a pas de lignes de commande.")
            if order.pos_order_id:
                raise UserError("Cette commande a déjà été traité.")
            # First, update order lines with warehouse info and colis numbers
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
            order.status = 'prepare'
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
                    'code_barre': line.product_id.default_code or line.product_id.default_code or '',
                })

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
        sequence = self._generate_pos_sequence(pos_config, session)
        pos_reference = self._generate_pos_reference(order, warehouse.name)

        pos_user = session.user_id or self.env.user

        pos_order_vals = {
            'name': sequence,
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
            return f"{base_reference}-{warehouse_name}-{uid}"
        else:
            return f"{base_reference}-{uid}"

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

    def _generate_pos_sequence(self, pos_config, session):
        return self.env['ir.sequence'].next_by_code('pos.order') or '/'



class StockWebsiteOrderLine(models.Model):
    _name = 'stock.website.order.line'
    _description = 'Ligne de commande du site'

    order_id = fields.Many2one('stock.website.order', string="Commande")
    product_id = fields.Many2one('product.product', string="Produit")
    product_name = fields.Char(string="Nom du Produit")
    quantity = fields.Float(string="Quantité")
    price = fields.Float(string="Prix")
    discount = fields.Float(string="Remise")

    magasin_name = fields.Char(string="Magasin", help="Nom du magasin où le produit est stocké")
    numero_colis = fields.Integer(string="Numéro Colis", help="Numéro de colis basé sur l'entrepôt de stock")
    code_barre = fields.Char(string="Code Barre", help="Code barre du produit")
    #payment = fields.Char(string="Mode de paiment")
