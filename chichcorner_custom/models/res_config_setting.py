# -*- coding: utf-8 -*-
###################################################################################
#
#    Copyright (c) 2023 tmistones.com
#
#
#
#
###################################################################################


from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_so_print_direct = fields.Boolean(
        string="Print direct SO", implied_group='tmi_print_direct_so.group_to_so_print_direct',
        help="Allows you to print SO")
