# Device approval stage 2 (not production ready)

Version 13.0.4.10.42 adds JSON-RPC endpoints:
- POST /api/driver/v1/device-approval/request
  params: device_id, device_name, database_name, server_origin, public_key, request_nonce (cryptographically random, 32+ chars)
- POST /api/driver/v1/device-approval/status
  params: request_nonce
- POST /api/driver/v1/device-approval/activate
  params: request_nonce, device_id, activation_code

All requests require an established Odoo database session, as with the existing API.
The administrative review screen is from stage 1. The approval code expires after five minutes and can only be consumed once.

**DO NOT INSTALL ON PRODUCTION YET.** The API transport is staged but cryptographic public-key validation, challenge signatures, token binding, enforcement on login and protected routes, client integration, company assignment policy, per-IP throttling, and tests remain incomplete. `activation_credential` is NOT YET an access credential and does not authorize API calls. The supplied public_key is recorded but not cryptographically verified.

Never interpret this stage as an anti-cloning or anti-token-theft defense.
