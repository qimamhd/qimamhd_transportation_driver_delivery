# Stage 3 — Ed25519 proof of possession (NOT ENFORCED)

This stage validates Ed25519 public keys at enrollment and adds one-time challenge/verify endpoints.

- `POST /api/driver/v1/device-approval/challenge`: JSON-RPC params `{approval_id, activation_credential}`; returns `{challenge, expires_in_seconds}`.
- `POST /api/driver/v1/device-approval/verify`: JSON-RPC params `{approval_id, activation_credential, challenge, signature}`; signature is unpadded base64url Ed25519 over UTF-8 `QIMAM-DEVICE-PROOF\n<database>\n<approval_id>\n<challenge>`.
- Challenge expires in 2 minutes, single use (including failed verification), one active challenge per approval.
- Requires `cryptography` Python library in the existing Odoo process. Do not install dependencies or restart production without review.
- The original stage 2 request must now supply a **real base64url Ed25519 public key**, not an arbitrary text string.
- IMPORTANT: No driver session binding or protected API enforcement exists yet. A successful verify response is NOT authorization to driver APIs. Flutter support and a server-side enforcement policy are still required.
- Do not deploy on production until end-to-end testing and security review. There is no test execution against Odoo in this package.
