# 13.0.4.10.13 - Driver self-service password change

- Adds authenticated `POST /api/driver/v1/change-password`.
- Requires the current password before accepting a new password.
- Stores only the existing PBKDF2 password hash; plaintext is never persisted or logged.
- Keeps the current verified session, revokes other active app sessions, and revokes biometric credentials.
- Preserves the approved single-device binding.
