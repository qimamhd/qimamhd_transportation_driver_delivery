# v13.0.4.1.3

- Keep `app_failed_attempts` at the actual lock threshold/count when an app login is locked.
- A locked account now shows 5 failed attempts instead of resetting the counter to 0 immediately.
- Manager manual unlock still resets `app_failed_attempts` to 0 and clears `app_locked_until`.
- Successful login after lock expiry still resets the counter and clears the lock.
- No changes to password hashing, identification login, API routes, settlement flow, or session handling.
