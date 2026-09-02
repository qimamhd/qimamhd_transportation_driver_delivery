# v13.4.5.0 - Delivery Period Management

Adds a dedicated company-level **إدارة فترات التوصيل** screen.

- One period per company/month/year.
- Manager explicitly opens/closes a period.
- Flutter `/delivery-period-options` returns only open periods from this table.
- A missing driver batch is created lazily on the first delivery for any open period, including historical months.
- An existing driver batch must still be `draft`; a completed/reviewed/approved/transferred/cancelled driver batch remains locked.
- `POST /deliveries` independently checks the company period, so a stale/manipulated client cannot submit to a closed or missing period.
- Closing a company period does not mutate historical driver batches, review decisions, settlements, or accounting records.
- Existing `/delivery-periods` history endpoint remains unchanged.
