# 13.0.4.10.8 - Manual destination source dropdown hardening

- Fixes the manual driver-request destination dropdown in Odoo 13 editable one2many rows.
- Keeps the existing computed `destination_path_ids`, onchange domains, name_search guard and server-side validation.
- Adds a non-stored searchable helper on destinations so the ORM filters destinations directly from the current Source through pricing, even if the editable-row helper M2M/context is stale.
- Preserves shared pricing (`company_id = False`) and current-company pricing behavior.
- No Flutter/API/GPS/UUID/Single Device/settlement logic was changed.
