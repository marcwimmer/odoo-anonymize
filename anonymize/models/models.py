from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class IrModel(models.Model):
    _inherit = 'ir.model'

    anonymize_erase = fields.Boolean("Anonymize Erase")
