# v13.0.4.3.0 - Flexible delivery periods and scalable history

- Adds additive `GET /api/driver/v1/delivery-period-options` for selecting current or past periods without creating empty batches.
- Hardens `GET /api/driver/v1/delivery-periods` with server-date/current-period metadata and state/year filters.
- Adds paged `GET /api/driver/v1/delivery-lines` for high-volume monthly history (review/GPS/date filters, newest first).
- `POST /deliveries` still uses the delivery date as the authoritative batch period, permits historical dates, rejects future dates, and optionally validates `period_month`/`period_year` when newer clients send them.
- `POST /complete-period` can close any existing current/past draft period and is idempotent for done/review/approved/transferred periods; future periods are rejected.
- Existing routes/payloads remain backward compatible; no database schema change.
