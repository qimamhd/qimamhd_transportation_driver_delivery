# 13.0.4.8.7 - Direct Delivery Auto Context

- Added dedicated API `GET /api/driver/v1/direct-delivery/setup`.
- Assigned vehicle is resolved from `product.product` / inherited `product.template` data using `car_driver_name`.
- The assigned vehicle `car_area_id` becomes the fixed direct-delivery source.
- Alternative cars are limited to vehicles with the same `car_area_id`.
- Added `POST /api/driver/v1/direct-delivery/match-destination` to auto-match the current driver GPS only against destinations priced under that source.
- Direct-delivery destination matching uses a dedicated 50 meter radius and chooses the nearest valid destination.
- `POST /deliveries` revalidates the same direct-delivery rules server-side when `submission_context=direct_delivery`, preventing forged car/source/destination values.
- Full-route delivery, generic master-data endpoints, offline queue policy, period policy, and existing company GPS policy remain unchanged.
