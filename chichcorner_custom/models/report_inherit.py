from odoo import models,api,_


class SaleDetailsReport(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    def _get_report_values(self, docids, data=None):
        report_values = super(SaleDetailsReport, self)._get_report_values(docids, data)

        current_session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not current_session:
            report_values['orders'] = []
            return report_values

        orders = self.env['pos.order'].search([('session_id', '=', current_session.id)])
        formatted_orders = []
        for order in orders:
            total_qty = sum(line.qty for line in order.lines)
            formatted_orders.append({
                'pos_reference': order.pos_reference,
                'qty': total_qty,
                'amount_total': order.amount_total,
            })

        report_values['orders'] = formatted_orders
        return report_values


class JournalReport(models.AbstractModel):
    _name = 'report.chichcorner_custom.journal_report_template'
    _description = 'Point of Sale Journal Report'

    def _get_refund_details(self, orders):
        refund_details = []
        for order in orders:
            for line in order.lines:
                if line.qty < 0:
                    refund_details.append({
                        'product_name': line.product_id.name,
                        'qty': abs(line.qty),
                        'amount': abs(line.price_subtotal_incl),
                        'ticket': order.pos_reference,
                        'cashier': order.user_id.name,
                    })
        return refund_details

    def _get_payment_details(self, orders):
        payment_details = {
            'Carte Bancaire': [],
            'Banque': [],
            'Chèque': [],
            'Chèque MDC': [],
            'Avoir': [],
            'Cash': [],
            'Virement': [],
            'totals': {}
        }

        for order in orders:
            for payment in order.payment_ids:
                method = payment.payment_method_id
                method_type = method.name
                journal_name = method.journal_id.name  # Get journal name dynamically
                banque = order.banque
                payment_info = {
                    'ticket': order.pos_reference,
                    'cashier': order.employee_id.name,
                    'amount': payment.amount,
                    'banque': banque,
                }

                if method_type == 'Carte Bancaire':
                    payment_info.update({'stan': payment.stan or 'pas de stan'})
                    payment_details['Carte Bancaire'].append(payment_info)
                elif method_type == 'Chèque':
                    payment_info.update({'cheque_number': payment.cheque_number or '', 'banque': payment.banque or ''})
                    payment_details['Chèque'].append(payment_info)
                elif method_type == 'Chèque MDC':
                    payment_info.update(
                        {'cheque_number': payment.cheque_number or '', 'cheque_date': payment.cheque_date or '',
                         'banque': payment.banque or ''})
                    payment_details['Chèque MDC'].append(payment_info)

                elif method_type == 'Avoir':
                    payment_details['Avoir'].append(payment_info)

                elif method_type == 'Virement':  # Handle Virement payments
                    payment_info.update({
                        'vir_number': payment.vir_number or '',
                        'num_client': payment.num_client or '',
                        'vir_montant': payment.vir_montant,
                        'date_commande': order.date_commande.strftime('%Y-%m-%d') if order.date_commande else ''
                    })
                    payment_details['Virement'].append(payment_info)

                elif journal_name.startswith('Espèces'):
                    payment_details['Cash'].append(payment_info)  # Group all cash payments under 'Cash'
                elif method_type == 'Banque':
                    payment_details['Banque'].append(payment_info)

                if method.name not in payment_details['totals']:
                    payment_details['totals'][method.name] = 0
                payment_details['totals'][method.name] += payment.amount

        return payment_details

    def _get_report_values(self, docids, data=None):
        session_id = docids[0] if docids else self.env.context.get('active_ids', [False])[0]
        if not session_id:
            return {}

        session = self.env['pos.session'].browse(session_id)
        config_id = session.config_id.id
        orders = self.env['pos.order'].search([
            ('session_id', '=', session_id),
            ('config_id', '=', config_id)
        ])

        formatted_orders = [{'pos_reference': order.pos_reference, 'qty': sum(line.qty for line in order.lines),
                             'amount_total': order.amount_total, 'currency': order.pricelist_id.currency_id} for order
                            in orders]

        payment_methods = []
        payment_data = {}

        for order in orders:
            for payment in order.payment_ids:
                method_name = payment.payment_method_id.name
                payment_data[method_name] = payment_data.get(method_name, 0) + payment.amount

        for method_name, amount in payment_data.items():
            payment_methods.append({'name': method_name, 'amount': amount})

        total_payments = sum(payment['amount'] for payment in payment_methods)
        currency = orders[0].pricelist_id.currency_id if orders else self.env.company.currency_id
        payment_details = self._get_payment_details(orders)
        refund_details = self._get_refund_details(orders)

        return {
            'doc': session,
            'docs': session,
            'orders': formatted_orders,
            'session_name': session.name,
            'config_name': session.config_id.name,
            'state': session.state,
            'payment_methods': payment_methods,
            'total_payments': total_payments,
            'payment_details': payment_details,
            'refund_details': refund_details,
            'currency': currency,
        }


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def get_bon_de_sortie_data(self):

        data = []
        for move in self.move_ids_without_package:
            data.append({
                'product': f"[{move.product_id.default_code or ''}] {move.product_id.name}",
                'quantity': move.quantity,
                'delivered': move.quantity
            })
        return data


class BonDeSortieReport(models.AbstractModel):
    _name = 'report.chichcorner_custom.report_bon_de_sortie'
    _description = 'Bon De Sortie Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)
        return {
            'docs': docs,
        }

