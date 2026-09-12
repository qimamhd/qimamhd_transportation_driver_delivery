# 13.0.4.10.0 - submission_context security hardening

- Rejects missing, blank, and unknown `submission_context` values.
- Accepts only `direct_delivery` and `route_trip`.
- Enforces the server-side company policy before accepting `route_trip`.
- Prevents a Direct Delivery request from dropping into the legacy/general GPS path by blanking the context.
- Does not change the Direct Delivery 50 m rule, GPS accuracy policy, pricing logic, period logic, offline policy, or Flutter app.
