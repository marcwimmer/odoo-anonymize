import os
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.tools.sql import column_exists, table_exists
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import random
import logging

logger = logging.getLogger(__name__)


def _get_max_column_width(cr, tablename, fieldname):
    sql = (
        "SELECT character_maximum_length "
        "FROM information_schema.columns "
        "WHERE table_name = %s  AND column_name = %s;"
    )
    cr.execute(
        sql,
        (
            tablename,
            fieldname,
        ),
    )
    return cr.fetchone()[0]


def tabletype(cr, tablename):
    sql = (
        "SELECT table_name, table_type "
        " FROM information_schema.tables "
        " WHERE table_schema = 'public' "
        f" AND table_name = '{tablename}';"
    )
    cr.execute(sql)
    rec = cr.fetchone()
    if not rec:
        return None
    ttype = rec[1]
    return {"BASE TABLE": "table", "VIEW": "view"}[ttype]


class Anonymizer(models.AbstractModel):
    _name = "frameworktools.anonymizer"
    _domains = [
        "hotmail.com",
        "gmail.com",
        "aol.com",
        "mail.com",
        "mail.kz",
        "yahoo.com",
    ]

    @api.model
    def _rename_logins(self):
        self.env.cr.execute("select id, login from res_users where id > 2;")
        for rec in self.env.cr.fetchall():
            login = f"user{rec[0]}"
            self.env.cr.execute(
                "update res_users set login = %s where id=%s", (login, rec[0])
            )

    @api.model
    def gen_phone(self):
        first = str(random.randint(00000, 99999))
        second = str(random.randint(10000, 99999)).zfill(7)

        last = str(random.randint(1, 99)).zfill(2)
        while last in ["1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888"]:
            last = str(random.randint(1, 9998)).zfill(4)

        return "{}/{}-{}".format(first, second, last)

    @api.model
    def get_one_random_domain(self, domains):
        return random.choice(domains)

    @api.model
    def generate_random_email(self):
        import names

        return (
            names.get_full_name().replace(" ", ".")
            + "@"
            + self.get_one_random_domain(self._domains)
        )

    def _delete_mail_tracking_values(self):
        import pudb;pudb.set_trace()
        for field in self.env["ir.model.fields"].search([("anonymize", "!=", False)]):
            self.env.cr.execute(
                """
                delete from mail_tracking_value where field = %s
                and
                mail_message_id in (select id from mail_message where model=%s)
            """,
                (field.name, field.model_id.model),
            )

    @api.model
    def _delete_critical_tables(self):
        self.env.cr.execute("delete from mail_mail;")

    @api.model
    def _run(self, force=False):
        if force:
            if force != self.env.cr.dbname:
                raise Exception(
                    "force must match the databasename {}".format(self.env.cr.dbname)
                )
        if not force and os.environ["DEVMODE"] != "1":
            return
        import names

        KEY = "db.anonymized"
        if (
            not force
            and self.env["ir.config_parameter"].get_param(key=KEY, default="0") == "1"
        ):
            return
        self.env["ir.model.fields"]._apply_default_anonymize_fields()
        self.env.cr.commit()

        self._rename_logins()

        self._delete_critical_tables()
        self._delete_mail_tracking_values()

        for field in self.env["ir.model.fields"].search([("anonymize", "!=", False)]):
            try:
                obj = self.env[field.model]
            except KeyError:
                continue
            table = obj._table
            cr = self.env.cr
            if not table_exists(cr, table):
                continue
            if not column_exists(cr, table, field.name):
                logger.info(f"Ignoring not existent column: {table}:{field.name}")
                continue

            # check if table is a view
            if tabletype(self.env.cr, table) == "view":
                continue

            cr.execute(
                'select id, "{}" from {} order by id desc'.format(field.name, table)
            )
            recs = cr.fetchall()
            logger.info(f"Anonymizing {len(recs)} records of {table}")
            logger.info(f"Anonymizing following column {field.name}")
            for i, rec in enumerate(recs, 1):
                values = []
                v = rec[1] or ""
                v = field._anonymize_value(v)
                if isinstance(v, str):
                    maxdblen = _get_max_column_width(self.env.cr, table, field.name)
                    if maxdblen is not None:
                        if maxdblen < len(v):
                            v = v[:maxdblen]

                cr.execute(
                    f'update {table} set "{field.name}" = %s where id = %s',
                    (
                        v,
                        rec[0],
                    ),
                )
                if not i % 500:
                    quote = i / len(recs) * 100
                    logger.info(f"{table} Done {i} of {len(recs)}: {quote:.1f}%")

        self.env["ir.config_parameter"].set_param(KEY, "1")
