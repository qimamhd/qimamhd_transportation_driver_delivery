# 13.0.4.10.11 - Delivery Details API

- Added `GET /api/driver/v1/delivery-details` for the mobile month-detail screen.
- Uses the existing Bearer authentication and scopes records to the authenticated driver/company.
- Supports month/year, paging, review state, GPS status, and request-date filters.
- Intentionally does not access or return trip-sheet images, image names, base64, or binary image fields.
- Existing `/api/driver/v1/delivery-lines` remains unchanged for backward compatibility.
