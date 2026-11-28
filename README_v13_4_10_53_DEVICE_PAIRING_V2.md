# 13.0.4.10.53 - Device activation by match code (stage 1, backend)

Behind the new company option `driver_app_device_pairing_v2` (off by default).
The old activation-code flow is unchanged.

- `POST /api/driver/v1/device-pairing/request`: identity + password (same lock rules as login)
  + Ed25519 public key + device id + request nonce. Creates a pending request linked to the
  driver and the driver's company; returns a 6-digit `match_code` and `server_time`.
  Works on http test servers (origin is taken from the request, not from the client).
- Odoo: the request shows the driver and the match code. "الرمز مطابق - موافقة" approves,
  binds the device to the driver (`app_device_id`) and revokes the driver's other devices,
  sessions and biometric credentials. Requests expire after 30 minutes.
- `POST /api/driver/v1/device-pairing/status`: signed by the device key
  (`QIMAM-PAIRING-STATUS\n<db>\n<request_nonce>\n<timestamp>\n<nonce>`, ±90 s, nonce single use).
  After approval it returns the one-time `activation_credential` and `approval_id`; then the
  existing challenge/verify and signed requests apply unchanged.
- `DEVICE_PROOF_EXPIRED` errors now include `details.server_time` for clock correction.

Module upgrade required. No app change in this stage.
