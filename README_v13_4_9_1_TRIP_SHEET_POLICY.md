# 13.0.4.9.1 — Trip Sheet Policy

- Adds company setting `driver_app_trip_sheet_required`.
- Default is disabled for backward compatibility.
- Exposes `trip_sheet_required` through `/api/driver/v1/app-policy`.
- `/deliveries` rejects missing trip sheet images when the company policy requires them.
- Image payload limit is 1.2 MB.
- The binary field uses `attachment=True`, so image bytes are stored as Odoo attachments/filestore instead of inflating the business table row.
