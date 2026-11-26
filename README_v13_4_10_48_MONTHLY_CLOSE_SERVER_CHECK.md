# 13.0.4.10.48 - Enforce the monthly close setting on the server

- `POST /api/driver/v1/complete-period` now returns `MONTHLY_CLOSE_DISABLED` (403) when the driver's
  `app_monthly_close_enabled` ("إظهار زر الأقفال") is off. The batch is not touched.
- Drivers with the setting on: no change.
- The current app (0.5.120+151) already hides the button when the setting is off and shows the server message on error.
- Field help text updated. No new fields, no migration, no app update.
