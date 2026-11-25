# 13.0.4.10.45 - Restore driver self-service password change

- Restores authenticated `POST /api/driver/v1/change-password` (removed in `873fafd`, original in `6b48f86`).
- The current app (0.5.120+151) already calls this route from the change-password screen.
- Requires the current password; new password must be 6-256 chars and differ from the current one.
- 5 wrong current-password attempts lock the driver login for 15 minutes (shared lockout counter).
- Keeps the current session, revokes other app sessions and biometric credentials, keeps device binding.
- Logs the change in the employee chatter. No new fields, no migration.
