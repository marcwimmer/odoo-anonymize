from odoo.addons.queue_job.job import job
import string
import random
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools.mail import html2plaintext
from .cities import city_names
from .cities import street_names


class Fields(models.Model):
    _inherit = "ir.model.fields"
    _domains = [
        "hotmail.com",
        "gmail.com",
        "aol.com",
        "mail.com",
        "mail.kz",
        "yahoo.com",
    ]

    firstnames = [
        "Jack",
        "Maria",
        "Claudia",
        "Agata",
        "Angelika",
        "Bianca",
        "Franz",
        "Josef",
        "Sepp",
        "Heinrich",
        "Max",
        "Kevin",
    ]
    anonymize = fields.Selection(
        [
            ["clear", "Clear"],
            ["fullname", "Name"],
            ["lastname", "Last-Name"],
            ["firstname", "First-Name"],
            ["street", "Street"],
            ["phone", "Phone"],
            ["city", "City"],
            ["email", "Email"],
            ["lorem_ipsum", "Lorem Ipsum"],
        ],
        "Anonymize",
    )
    anonymize_length = fields.Integer("Anonymize Length")

    @api.model
    def gen_phone(self):
        first = str(random.randint(00000, 99999))
        second = str(random.randint(10000, 99999)).zfill(7)

        last = str(random.randint(1, 99)).zfill(2)
        while last in ["1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888"]:
            last = str(random.randint(1, 9998)).zfill(4)

        return "{}/{}-{}".format(first, second, last)

    @api.constrains("anonymize")
    def _check_anonymize_flag(self):
        for self in self:
            if self.ttype not in ["char", "text"]:
                raise ValidationError("Only chars can be anonymized!")

    @api.model
    def _apply_default_anonymize_fields(self):
        if self.search_count([("anonymize", "!=", False)]):
            return

        for dbfield in self.env["ir.model.fields"].search(
            [("ttype", "in", ["char", "text"])]
        ):
            for x in [
                ("phone", "phone"),
                ("lastname", "lastname"),
                ("firstname", "firstname"),
                ("city", "city"),
                ("zip", "number", 5),
                ("fax", "phone"),
                ("email", "email"),
            ]:
                self.env.cr.execute(
                    "update ir_model_fields set anonymize = %s where id = %s",
                    (
                        x[1],
                        dbfield.id,
                    ),
                )
                if len(x) > 2:
                    self.env.cr.execute(
                        "update ir_model_fields set anonymize_length = %s where id = %s",
                        (
                            x[2],
                            dbfield.id,
                        ),
                    )

        for dbfield in self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "in", ["display_name", "name"])]
        ):
            self.env.cr.execute(
                "update ir_model_fields set anonymize = 'fullname'  where id = %s",
                (dbfield.id,),
            )

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

    @api.model
    def lorem_ipsum(self, val):
        val = html2plaintext(val or "")
        alphabet = string.ascii_lowercase
        cipher_dict = {}

        for letter in alphabet:
            cipher_dict[letter] = random.choice(alphabet)
            cipher_dict[letter.upper()] = random.choice(alphabet).upper()
        for digit in string.digits:
            cipher_dict[digit] = random.choice(string.digits)
        cipher_dict.update({" ": " "})
        cipher_dict.update({p: p for p in string.punctuation})
        for C in "\n\t\l\r":
            cipher_dict.update({C: C})

        val2 = ""
        for letter in val:
            val2 += cipher_dict.get(letter, "")
        return val2.strip()

    def _anonymize_value(self, val):
        import names

        if self.anonymize == "fullname":
            return names.get_full_name()
        elif self.anonymize == "lastname":
            return names.get_last_name()
        elif self.anonymize == "email":
            return self.generate_random_email()
        elif self.anonymize == "phone":
            return self.gen_phone()
        elif self.anonymize == "city":
            return random.choice(city_names)
        elif self.anonymize == "street":
            return random.choice(street_names)
        elif self.anonymize == "firstname":
            return random.choice(self.firstnames)
        elif self.anonymize == "lorem_ipsum":
            return self.lorem_ipsum(val)
        elif self.anonymize == "clear":
            if self.ttype in ["char", "text"]:
                return ""
            elif self.ttype in ["date", "datetime"]:
                return None
            elif self.ttype in ["int", "float"]:
                return 0
            else:
                raise NotImplementedError(self.type)
        else:
            raise NotImplementedError(self.anonymize)

    def write(self, vals):
        if "anonymize" in vals:
            anonymize = vals.pop("anonymize")
            for rec in self:
                self.env.cr.execute(
                    "update ir_model_fields set anonymize = %s where id = %s",
                    (
                        anonymize,
                        rec.id,
                    ),
                )

        res = super().write(vals)
        return res
