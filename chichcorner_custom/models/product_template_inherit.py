from odoo import api, fields, models, tools

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_print_product_pdf(self):
        return self.env.ref('chichcorner_custom.action_product_template_pdf').report_action(self)
