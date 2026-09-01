# v13.0.4.2.0 - Backend Security RC

Security hardening release that preserves the approved driver-delivery business flow and API v1 contracts.

## Changes
- Removed the temporary `/api/driver/v1/login_test` route completely.
- Added safe public `/api/driver/v1/ping` for mobile server-connection setup. It exposes no DB/company/Odoo internals.
- Added defensive request-size and credential-length bounds.
- Added Bearer header/token length bounds.
- Preserved generic login errors to avoid identity/account enumeration.
- Preserved password hashing, login lockout, manager unlock, token hash storage, revoke/expiry behavior.
- Closed UUID concurrent-submit race using PostgreSQL unique constraint + savepoint recovery.
- Closed monthly-batch concurrent-create race using existing SQL uniqueness + savepoint recovery.
- Session lifetime remains 30 days by default but may be shortened using system parameter `qimamhd_transportation_driver_delivery.session_days` (1..30).
- Technical exceptions are not returned by delivery/session creation paths.

## Deployment requirements (outside addon code)
- Production mobile access must use HTTPS.
- Do not expose Odoo application port directly to the Internet; proxy through Nginx/HTTPS.
- Apply Nginx rate limiting to `/api/driver/v1/login` and a request-body limit.
- Keep PostgreSQL private.
- Disable database listing and configure dbfilter for customer domains.

## Deliberately unchanged
- API v1 endpoint names and payloads used by the mobile app.
- Identification ID + password login.
- 5-attempt / 15-minute driver lock policy.
- 30-day default session expiry.
- UUID idempotency semantics.
- GPS validation/review workflow.
- Monthly batch/review/approval/settlement/rollback concepts.
- Company-level car list behavior (requires a confirmed driver-car assignment relation before narrowing).
