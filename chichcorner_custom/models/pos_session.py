from odoo import api, fields, models, tools
from odoo.exceptions import UserError, AccessError
import re
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    loyalty_card_ids = fields.One2many('loyalty.card', 'source_pos_order_id', string='Loyalty Cards')
    related_loyalty_cards = fields.Many2many('loyalty.card', compute='_compute_related_loyalty_cards', string='Related Loyalty Cards')

    loyalty_cards_id = fields.Many2one('loyalty.card', string='Loyalty Card')

    def _prepare_order(self, order):
        res = super(PosOrder, self)._prepare_order(order)
        res['loyalty_cards_id'] = order.get('loyalty_cards_id')
        return res

    def _compute_related_loyalty_cards(self):
        for order in self:
            order.related_loyalty_cards = order.loyalty_card_ids

    def get_loyalty_cards_info(self):
        for order in self:
            # Get all loyalty cards linked to this order
            loyalty_cards = order.loyalty_card_ids
            loyalty_cards_info = []

            for card in loyalty_cards:
                loyalty_cards_info.append({
                    'code': card.code,
                    'points': card.points,
                })

            return loyalty_cards_info


class PosSession(models.Model):
    _inherit = 'pos.session'


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    gift_card_code = fields.Char(string='Gift Card Code', compute='_compute_gift_card_code', store=True)

    loyalty_code = fields.Char(related='coupon_id.code', string='Loyalty Code', readonly=True)
    loyalty_points = fields.Float(related='coupon_id.points', string='Points', readonly=True)

    order_loyalty_cards = fields.Many2many('loyalty.card', compute='_compute_order_loyalty_cards',
                                           string='Order Loyalty Cards')

    @api.depends('order_id.loyalty_card_ids')
    def _compute_order_loyalty_cards(self):
        for line in self:
            line.order_loyalty_cards = line.order_id.loyalty_card_ids