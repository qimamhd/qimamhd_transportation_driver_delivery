# 13.0.4.10.10 - Manual destination filter rewrite

- Rewrote only the manual-entry Destination dropdown filtering.
- Destination candidates now come directly from `trnsp.store.pricing.lines` filtered by the row `source_path_id` and company.
- Removed the manual Destination field dependency on the `driver_app_source_ids` / `name_search` context mechanism.
- The editable one2many onchange now writes `destination_path_ids` immediately and returns the same domain.
- Existing server-side route validation remains intact.
- Car and Source filtering, APIs, GPS, UUID/idempotency, device security, settlement logic and Flutter contracts are unchanged.
