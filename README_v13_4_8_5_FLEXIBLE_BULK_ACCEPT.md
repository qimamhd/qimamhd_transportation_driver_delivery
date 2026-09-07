# 13.0.4.8.5 - Flexible bulk acceptance

- `قبول جميع السطور` accepts all pending GPS-valid deliveries and skips pending GPS-problem lines instead of raising an error.
- Existing exceptional GPS acceptance remains authoritative and does not block bulk acceptance.
- `اعتماد` now reports unresolved GPS-problem lines, so the blocking message appears at final approval where it belongs.
- Once an out-of-range line is accepted through `قبول استثنائي`, final approval proceeds normally (provided there are no other pending/rejected validation issues).
- No API, GPS calculation, delivery creation, company policy, period, settlement, or mobile-app behavior was changed.
