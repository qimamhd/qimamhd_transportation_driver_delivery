# 13.0.4.10.12 - Manual destination domain and time fix

- Fixed the manual destination picker domain to use only the real relation available in Odoo 13: `trnsp.store.pricing.lines.header_id.source_path_id`.
- Removed the invalid `header_id.company_id` XML domain that caused `Invalid field company_id` on `trnsp.store.pricing`.
- Manual line default time now uses `HH:MM` (hours and minutes only) from the company driver-app timezone.
- Existing API-provided request times remain accepted, including legacy `HH:MM:SS` values.
- No API, GPS, UUID, single-device, settlement, car filter, or source filter logic changed.
