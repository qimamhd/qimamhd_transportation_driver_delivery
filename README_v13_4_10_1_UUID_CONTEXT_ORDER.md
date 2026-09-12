# 13.0.4.10.1 - UUID/context validation order

Surgical security follow-up to 13.0.4.10.0.

- Validates `submission_context` before the UUID idempotency early-return.
- A replayed UUID with a missing/unknown context now returns `INVALID_SUBMISSION_CONTEXT` (409) instead of a successful duplicate response.
- Keeps duplicate/idempotency behavior unchanged for valid contexts.
- No changes to GPS calculations, 50m direct-delivery radius, GPS accuracy policy, vehicle/source/destination validation, route-trip policy, company policies, trip-sheet policy, or Flutter.
