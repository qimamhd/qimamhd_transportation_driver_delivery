# 13.0.4.10.12 - Minimal delivery-details diagnostic

Only `/api/driver/v1/delivery-details` payload was reduced for transport diagnosis.
Each line returns only: `id`, `request_date`, `request_time`, `review_state`.
No images/binary fields, GPS, notes, car/source/destination names, or other relational payloads are read or returned by this serializer.
Legacy APIs and home/create-delivery flows are unchanged.
