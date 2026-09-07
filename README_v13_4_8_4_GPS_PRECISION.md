# 13.0.4.8.4 - GPS coordinate precision

- Increased `gbs_from` and `gbs_to` precision on `trnsp.store.pricing.lines` to 7 decimal places.
- This prevents destination coordinates entered in Odoo from being rounded to two decimal places.
- No change to GPS radius logic, Haversine calculation, driver-app policies, delivery submission, periods, or offline behavior.
- Existing destination coordinates that were already saved rounded must be re-entered after upgrading the module.
