# 13.0.4.10.52 - Daily cleanup of proof nonces and old sessions

- New daily cron "Driver App - Cleanup Old Proof Nonces and Sessions"
  (`trnsp.driver.device.proof.nonce._cron_cleanup_driver_app_records`).
- Deletes proof nonces older than 1 day (proofs older than 90 seconds are already rejected).
- Deletes app sessions and biometric credentials expired or revoked more than 30 days ago.
- Active sessions and delivery data are untouched. Module upgrade only, no app update.
