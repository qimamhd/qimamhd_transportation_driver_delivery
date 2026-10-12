# Stage 4: optional per-request Ed25519 enforcement (NOT production ready)

Adds opt-in company flag `driver_app_device_proof_required` (default OFF). When ON, login and every API endpoint using `authenticate_driver()` require Ed25519 request proof.

Headers: `X-Qimam-Approval`, `X-Qimam-Timestamp` (Unix seconds), `X-Qimam-Nonce` (base64url 32-96 characters), `X-Qimam-Signature` (base64url Ed25519 signature).

Signed UTF-8 text is joined by LF in this order: `QIMAM-REQUEST-V1`, database, approval id, timestamp, nonce, uppercase HTTP method, request path, SHA256 hex of raw request body, SHA256 hex of Bearer token (empty for login).

The nonce is inserted atomically into `trnsp.driver.device.proof.nonce` with a unique `(approval_id, nonce)` constraint. Use a fresh nonce for every request, including retries. Clock skew: 90 seconds.

## WARNING
- Flutter client does not yet sign requests. **DO NOT ENABLE FLAG.**
- `cryptography` must be installed in the Odoo runtime. Do not install or restart on production without staging validation.
- Not all controllers may call `authenticate_driver()`. Audit ALL API routes before enabling.
- Existing device binding must be established and the approval company/device must match; admin must correctly associate approval with company.
- Existing unauthenticated approval endpoints still require hardening/rate limits.
- Database nonce rows require retention cleanup; not yet provided.
- No live Odoo integration test has been run.
