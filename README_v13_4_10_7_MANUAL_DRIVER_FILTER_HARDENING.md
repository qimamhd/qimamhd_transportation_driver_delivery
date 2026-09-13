# 13.0.4.10.7 — Manual Driver Entry Filtering Hardening

## Scope
Surgical hardening of manual delivery-line entry in Odoo only. Flutter/API contracts are unchanged.

## Changes
- Centralized allowed car resolution from the driver assigned car `car_area_id` and company.
- Source list is locked to the driver's assigned operational area when that source is priced.
- Destination list is derived only from pricing lines for the selected allowed source and company.
- Car/source changes clear stale incompatible destination values in the editable one2many UI.
- Added server-side validation for car area/company, source area, and destination/source relationship so RPC/import cannot bypass UI domains.
- Preserved shared records (`company_id = False`) and existing settlement/API/GPS/UUID/security logic.

## Validation
- Python syntax compile.
- XML parse.
- Manifest/version check.
- Static diff review.

Runtime Odoo execution was not performed in this workspace.
