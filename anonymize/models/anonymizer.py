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
        for field in self.env["ir.model.fields"].search([("anonymize", "!=", False)]):
            self.env.cr.execute(
                """
                delete from mail_tracking_value where field = %s
                and
                mail_message_id in (select id from mail_message where model=%s)
            """,
                (field.id, field.model_id.model),
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
        dbfields = self.env["ir.model.fields"].search(
            [("anonymize", "!=", False)], order="model"
        )
        models = dbfields.mapped("model")
        for model in models:
            logger.info(f"Anonymizing model {model}")

            try:
                obj = self.env[model]
            except KeyError:
                continue
            table = obj._table
            cr = self.env.cr
            if not table_exists(cr, table):
                continue

            # check if table is a view
            if tabletype(self.env.cr, table) == "view":
                continue
            model_dbfields = dbfields.filtered(lambda x: x.model == model)
            effective_fields = model_dbfields.browse()

            for field in model_dbfields:
                if not column_exists(cr, table, field.name):
                    logger.info(f"Ignoring not existent column: {table}:{field.name}")
                else:
                    effective_fields |= field

            if not effective_fields:
                continue
            sql_fields = ",".join(sorted(effective_fields.mapped("name")))
            cr.execute(f"select id, {sql_fields} from {table} order by id desc")
            recs = cr.dictfetchall()
            new_values = self._anonymize_records(recs, effective_fields, table)
            self._update_table_with_new_values(table, new_values)

        self.env["ir.config_parameter"].set_param(KEY, "1")

    def _anonymize_records(self, recs, model_dbfields, table):
        res = []
        logger.info(f"Generating anonymizing {len(recs)} records of {table}")
        for i, rec in enumerate(recs):
            new_rec = {"id": rec["id"]}
            if not i % 100:
                quote = round(i / len(recs) * 100, 1)
                logger.info(
                    f"Anonymizing values {table} - "
                    f"progress: {i + 1} of {len(recs)} {quote}%"
                )

            for field in model_dbfields:
                v = field._anonymize_value(rec[field.name] or "")
                if isinstance(v, str):
                    maxdblen = _get_max_column_width(self.env.cr, table, field.name)
                    if maxdblen is not None:
                        if maxdblen < len(v):
                            v = v[:maxdblen]

                new_rec[field.name] = v

            res.append(new_rec)
        return res

    def _update_table_with_new_values(self, table, new_values):
        if not new_values:
            return

        sql_fields = list(sorted(filter(lambda x: x != "id", new_values[0].keys())))
        updates = []
        for field in sql_fields:
            updates.append(f" {field} = %s")
        sql_updates = ",".join(updates)
        del updates

        for i, rec in enumerate(new_values):
            sql_values = [rec[x] for x in sql_fields]
            self.env.cr.execute(
                f'update {table} set {sql_updates} where id = %s',
                tuple(sql_values + [rec["id"]]),
            )
            if not i % 100:
                quote = round(i / len(new_values) * 100, 1)
                logger.info(
                    f"{table} Writing to database done {i} of "
                    f"{len(new_values)}: {quote:.1f}%"
                )
                self.env.cr.commit()
