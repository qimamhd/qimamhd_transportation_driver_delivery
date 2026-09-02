# 13.0.4.4.0 - Server Controlled Delivery Periods

- Odoo is now authoritative for which periods the driver may submit to.
- `GET /api/driver/v1/delivery-period-options` returns only allowed periods:
  - current month when its batch is missing or still draft;
  - historical months only when that driver's existing batch is explicitly draft.
- Closed/review/approved/transferred/cancelled periods are not returned as delivery options.
- `POST /api/driver/v1/deliveries` no longer auto-creates a historical batch. A past period without an existing draft batch returns `PERIOD_NOT_OPEN`.
- Current-month first submission remains backward compatible: its batch is created automatically.
- No database schema changes were introduced.
- History endpoint `/delivery-periods`, review, approval, transfer, rollback, GPS, UUID and settlement behavior are unchanged.

## Back-office operation
To allow a driver to submit to a previous month, create that driver's monthly batch in Odoo for the required month/year in draft state, or reopen an eligible existing batch back to draft. The mobile app will then show that period automatically.
