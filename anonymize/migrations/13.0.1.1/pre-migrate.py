from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    cr.execute("alter table ir_model_fields rename anonymize to anonymize_old")
    cr.execute("alter table ir_model_fields add anonymize varchar;")
    cr.execute("update ir_model_fields set anonymize='name' where anonymize_old")