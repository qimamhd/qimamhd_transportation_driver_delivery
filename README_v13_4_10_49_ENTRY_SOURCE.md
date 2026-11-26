# 13.0.4.10.49 - Mark delivery source and lock app coordinates

- New field `entry_source` ("المصدر") on `trnsp.store.driver.request.line`: `app` or `manual`.
  - `POST /api/driver/v1/deliveries` sets `app`; any other create (Odoo manual entry) sets `manual`.
  - Existing rows are left empty (origin unknown). No field default, so the upgrade does not touch old rows.
- Driver latitude/longitude can no longer be changed on `app` lines (server check + readonly in the batch form).
  Manual lines keep the current behaviour.
- `entry_source` itself cannot be written after create.
- Shown as a column in the batch deliveries list. No app update needed.
