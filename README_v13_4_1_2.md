# v13.0.4.1.2

- Added manager-only **فك قفل دخول التطبيق** button on the driver employee app tab.
- The action resets only `app_failed_attempts` and `app_locked_until`.
- It does not change the password, identification ID, app access flag, biometric flag, or active sessions.
- The button is hidden when there are no failed attempts and no active lock.
- Existing v13.0.4.1.1 login error handling remains unchanged.
