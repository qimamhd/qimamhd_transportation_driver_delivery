# 13.0.4.6.1 — Login branding endpoint

Adds `GET /api/driver/v1/branding` for the Qimam Route login UI.

The endpoint is public because it is needed before authentication, but it returns only the company display name and company logo. It intentionally does not expose database names, Odoo versions, company IDs, users, branches, paths, or infrastructure details.

No delivery, GPS, review, settlement, period, session, or authentication logic was changed.
