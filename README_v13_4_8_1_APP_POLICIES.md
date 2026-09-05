# v13.0.4.8.1 — Driver App Company Policies

Adds a dedicated **Driver App Settings** tab on `res.company` while preserving all existing workflows for optional reuse.

Defaults per company:
- GPS: strict / inside destination radius only.
- Periods: current server month only.
- Offline creation: disabled.
- Delivery datetime: trusted server time.
- Previous months: auto-close enabled.

Optional policies can restore the previous behavior without deleting its code:
- outside-GPS deliveries can enter review,
- backend-managed delivery periods can be used,
- offline queue can be enabled,
- driver date/time selection can be enabled.

Security authority remains server-side. The phone clock cannot move a strict/current-month/server-time delivery into another month.
