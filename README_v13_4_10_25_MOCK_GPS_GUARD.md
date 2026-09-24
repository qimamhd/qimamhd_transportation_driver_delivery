# 13.0.4.10.25 - Optional Mock GPS Guard

- Adds company option `driver_app_mock_gps_protection`, disabled by default.
- Exposes `mock_gps_protection_enabled` through `/api/driver/v1/app-policy`.
- When disabled, the legacy GPS flow is unchanged.
- When enabled, mobile clients can block Android locations marked as mock and the final delivery API rejects an explicit `location_is_mocked=true`.
- Existing destination radius and GPS accuracy rules are unchanged.
