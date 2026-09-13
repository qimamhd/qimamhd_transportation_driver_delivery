# 13.0.4.10.6 - Manual Driver Request Filters

Surgical UI/domain hardening for manually-added driver-app request lines.

- Default car remains the driver's assigned car.
- Car dropdown is restricted to non-trailer cars in the same `car_area_id` as the driver's assigned car, company-scoped.
- Source defaults to the assigned car's `car_area_id` and the source dropdown exposes only that source when it has pricing configuration.
- Destination dropdown is restricted to destinations configured under that source, company-scoped.
- Saved rows use `batch_id` as authority; unsaved inline rows use the parent driver/company context already supplied by the form.
- Existing create/save validation remains intact as a server-side safety layer.
- No changes to API, GPS, periods, offline policy, settlement rules, security/session logic, or Flutter.
