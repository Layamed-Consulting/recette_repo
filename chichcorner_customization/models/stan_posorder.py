from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)
from collections import defaultdict

class AccountJournal(models.Model):
    _inherit = 'pos.order'

    stan = fields.Char(string='STAN Number',readonly=True, help='System Trace Audit Number for the journal entry.')

    def _order_fields(self, ui_order):
        result = super()._order_fields(ui_order)
        _logger.debug("UI Order: %s", ui_order)  # Log the ui_order for debugging
        result['stan'] = ui_order.get('stan')
        return result

    def confirm_coupon_programs(self, coupon_data):
        """Override to prevent creating loyalty points for client ID 34 on loyalty programs"""
        get_partner_id = lambda pid: pid and self.env['res.partner'].browse(pid).exists() and pid or False
        coupon_data = {int(k): v for k, v in coupon_data.items()}

        self._check_existing_loyalty_cards(coupon_data)
        coupon_new_id_map = {k: k for k in coupon_data.keys() if k > 0}

        # Filter out loyalty programs for client ID 34
        filtered_coupon_data = {}
        for cid, data in coupon_data.items():
            partner_id = data.get('partner_id')
            program_id = data.get('program_id')

            program = self.env['loyalty.program'].browse(program_id).exists()
            partner = self.env['res.partner'].browse(partner_id).exists()

            if partner and program.program_type == 'loyalty':
                if 'FID' not in partner.category_id.mapped('display_name'):
                    # Skip creation of loyalty points for NOTVIP clients
                    continue

            filtered_coupon_data[cid] = data

        # Use the original logic, but with filtered coupon_data
        coupon_data = filtered_coupon_data

        # --- Begin original logic from Odoo ---
        coupons_to_create = {k: v for k, v in coupon_data.items() if k < 0 and not v.get('giftCardId')}
        coupon_create_vals = [{
            'program_id': p['program_id'],
            'partner_id': get_partner_id(p.get('partner_id', False)),
            'code': p.get('barcode') or self.env['loyalty.card']._generate_code(),
            'points': 0,
            'source_pos_order_id': self.id,
        } for p in coupons_to_create.values()]

        new_coupons = self.env['loyalty.card'].with_context(action_no_send_mail=True).sudo().create(coupon_create_vals)

        gift_cards_to_update = [v for v in coupon_data.values() if v.get('giftCardId')]
        updated_gift_cards = self.env['loyalty.card']
        for coupon_vals in gift_cards_to_update:
            gift_card = self.env['loyalty.card'].browse(coupon_vals.get('giftCardId'))
            gift_card.write({
                'points': coupon_vals['points'],
                'source_pos_order_id': self.id,
                'partner_id': get_partner_id(coupon_vals.get('partner_id', False)),
            })
            updated_gift_cards |= gift_card

        for old_id, new_id in zip(coupons_to_create.keys(), new_coupons):
            coupon_new_id_map[new_id.id] = old_id

        all_coupons = self.env['loyalty.card'].browse(coupon_new_id_map.keys()).exists()
        lines_per_reward_code = defaultdict(lambda: self.env['pos.order.line'])
        for line in self.lines:
            if not line.reward_identifier_code:
                continue
            lines_per_reward_code[line.reward_identifier_code] |= line
        for coupon in all_coupons:
            if coupon.id in coupon_new_id_map:
                coupon.points += coupon_data[coupon_new_id_map[coupon.id]]['points']
            for reward_code in coupon_data[coupon_new_id_map[coupon.id]].get('line_codes', []):
                lines_per_reward_code[reward_code].coupon_id = coupon

        new_coupons.with_context(action_no_send_mail=False)._send_creation_communication()

        report_per_program = {}
        coupon_per_report = defaultdict(list)
        for coupon in new_coupons | updated_gift_cards:
            if coupon.program_id not in report_per_program:
                report_per_program[coupon.program_id] = coupon.program_id.communication_plan_ids.\
                    filtered(lambda c: c.trigger == 'create').pos_report_print_id
            for report in report_per_program[coupon.program_id]:
                coupon_per_report[report.id].append(coupon.id)

        return {
            'coupon_updates': [{
                'old_id': coupon_new_id_map[coupon.id],
                'id': coupon.id,
                'points': coupon.points,
                'code': coupon.code,
                'program_id': coupon.program_id.id,
                'partner_id': coupon.partner_id.id,
            } for coupon in all_coupons if coupon.program_id.is_nominative],
            'program_updates': [{
                'program_id': program.id,
                'usages': program.total_order_count,
            } for program in all_coupons.program_id],
            'new_coupon_info': [{
                'program_name': coupon.program_id.name,
                'expiration_date': coupon.expiration_date,
                'code': coupon.code,
            } for coupon in new_coupons if (
                coupon.program_id.applies_on == 'future'
                and coupon.program_id.program_type not in ['gift_card', 'ewallet']
            )],
            'coupon_report': coupon_per_report,
        }

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result["search_params"]["fields"].append("category_id")  # Load M2M field
        return result

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        result += ['res.partner.category']  # Load category model into POS
        return result

    def _loader_params_res_partner_category(self):
        """Define what fields to load for partner categories"""
        return {
            'search_params': {
                'fields': ['name', 'display_name'],
            },
        }

    def _get_pos_ui_res_partner_category(self, params):
        """Load partner categories for POS"""
        return self.env['res.partner.category'].search_read(**params['search_params'])

