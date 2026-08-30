# QimamHD Transportation Driver Delivery

Odoo 13 add-on for driver application access and intermediate monthly restaurant delivery review.

## Dependency
- `qimamhd_transportation_v2_13`

## Technical module name
- `qimamhd_transportation_driver_delivery`

The module is independent from the base transportation module and extends it using `_inherit` and inherited XML views.


## Preflight check

Before deploying or pushing changes, run:

```bash
python3 tools/preflight_check.py
```

The script checks Python compilation, XML parsing, Odoo 13 label rules, XPath syntax, duplicate XML IDs, manifest data paths, access CSV structure, object-button methods, the base-module dependency, and stale technical-module references.

A final install/upgrade on an Odoo 13 test database is still required because inherited views and external IDs are resolved by the live Odoo registry.


## 13.0.4.0.5
- Validate and normalize delivery time before period-lock checks; invalid time returns `INVALID_TIME`.
- Invalid delivery dates now return a clear Arabic `INVALID_DATE` response.
- Repeating `complete-period` for an already completed batch is idempotent and returns success with `already_completed=true`.
- Prevent accepting a delivery line when GPS is invalid; rejection remains available for review.


## v13.0.4.0.9 - Safe settlement rollback
- Each app batch creates a dedicated legacy driver settlement in draft; it is no longer merged into an accountant-created draft.
- Added explicit ownership link from settlement to app batch and from batch to generated settlement.
- Added manager-only `التراجع عن التحويل` with confirmation.
- Rollback is allowed only while the settlement is draft, deletes that dedicated settlement, clears line transfer links, and returns the batch to `approved`.
- From `approved`, manager can either transfer again or use `إعادة فتح` so the driver can submit forgotten deliveries; reopening resets review decisions to pending.
- Added guarded migration rollback for a v13.0.4.0.8 settlement only when ownership can be proven from line links and quantities.
