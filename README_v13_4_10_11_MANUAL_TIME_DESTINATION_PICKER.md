# 13.0.4.10.11 — Manual Time + Destination Picker

- Manual driver-request rows default `request_time` from the company driver-app timezone using the same trusted company clock as the API.
- Reworked only the manual destination selector: it now selects directly from `trnsp.store.pricing.lines` with a domain on the current `source_path_id` and company.
- The selected pricing line writes back to the existing `destination_path_id` / `pricing_line_id`, so GPS, settlement, API, and existing business logic continue using the original fields.
- Existing destination server-side validation remains in place.
- Car/source filtering, APIs, UUID, GPS rules, single-device security, and settlement logic were not redesigned.
