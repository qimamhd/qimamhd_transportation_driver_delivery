# 13.0.4.10.5 — Destination-controlled GPS radius

- GPS accuracy remains company-controlled through `driver_app_max_gps_accuracy`.
- Allowed destination range is taken only from each pricing destination line `gps_radius`.
- Direct Delivery no longer uses a fixed 50 m radius; matching and final server validation use the matched destination's own radius.
- Pricing header now includes a bulk radius helper and an explicit button to apply it to all destination lines under that source.
- Existing per-destination radius remains editable for exceptions after bulk update.
- No changes to period policy, offline policy, single-device security, trip-sheet policy, vehicle/source restrictions, idempotency, or settlement logic.
