# 13.0.4.10.15 — Driver destination check (diagnostic only)

- Adds `hr.employee.app_destination_check_enabled`, disabled by default.
- Exposes the flag only in the authenticated direct-delivery setup payload.
- Reuses the existing `/destinations?source_id=...` endpoint, which already scopes destinations to the driver's company and selected/assigned source.
- The mobile feature is diagnostic only: it does not change destination IDs, GPS matching, radius validation, submission payloads, or create/update records.
