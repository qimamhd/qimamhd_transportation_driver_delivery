# v13.0.4.1.1

- Fixes driver API login error handling after switching the username to `hr.employee.identification_id`.
- Login runtime metadata writes (`app_failed_attempts`, `app_locked_until`, `app_last_login`) no longer invoke full app configuration validation.
- A driver with no configured application password now receives a normal `INVALID_CREDENTIALS` response instead of an Odoo `ValidationError`/server error during a failed login attempt.
- Existing password hashing and minimum password length policy are unchanged.
