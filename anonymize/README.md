# anonymize

Anonymizes personal data in an Odoo database so a production dump can be used
for development/testing without exposing real personal data.

Usually called with:

    odoo anonymize

## How it works

1. Marks char/text fields whose name contains a PII hint (`email`, `phone`,
   `fax`, `firstname`, `lastname`, `city`, `zip`) plus `res.partner` name /
   display_name, via `_apply_default_anonymize_fields`.
2. Replaces the marked field values with fake data.
3. Renames logins, deletes `mail_mail` and mail tracking values.
4. Runs `_anonymize_extra_gaps` for PII the name heuristic does not catch
   (see below).
5. Sets `db.anonymized = 1`.

### Set-based (bulk) anonymization

Field values are anonymized with **one bulk `UPDATE` per table** (SQL
expressions, id-based fake values), not row-by-row. On large databases this is
orders of magnitude faster (minutes instead of hours) and does not blow up
memory. Translatable (`jsonb`) columns are wrapped in `jsonb_build_object`.

### Coverage beyond the name heuristic (`_anonymize_extra_gaps`)

The name-based heuristic misses several personal-data columns; these are
handled explicitly:

- **Addresses:** `res_partner.street*` (not matched by any hint).
- **`mobile`** (does not contain the substring "phone").
- **Stored/computed name fields** not refreshed after anonymizing `name`
  (`complete_name`, `display_name_no_ref`, `commercial_company_name`,
  `search_name`).
- **`vat`**.
- **Bank data:** `res_partner_bank.acc_holder_name`, `acc_number`,
  `sanitized_acc_number` (kept non-IBAN-shaped on purpose).
- **`pre_partner`** (import staging) has its own `name`/`display_name`/
  `street*`/`mobile`/`vat`/... which are anonymized directly.
- **User/login tables:** `partner_inls_user.name`, `sub_user.name`,
  `partner_registration.user_name`.
- **Free-text:** `*.order_comment`, `res_users.signature`,
  `mail_alias.alias_full_name`, `zbs_mapper.comment`, etc.

Customer/address reference numbers (`res_partner.*ref`) are intentionally left
untouched because they can carry referential meaning.

### Notes / Odoo 18 fixes

- `firstname` anonymize type is implemented (`names.get_first_name`).
- Translatable char/text columns are stored as `jsonb` in Odoo 16+ and are
  written accordingly (a raw string `UPDATE` would fail with
  "invalid input syntax for type json").
- Requires the python packages `names` and `arrow` in the Odoo environment.

## Authors

* Marc Wimmer <marc@itewimmer.de>
