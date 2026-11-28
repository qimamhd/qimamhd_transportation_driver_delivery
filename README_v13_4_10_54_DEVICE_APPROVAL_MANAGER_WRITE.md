# 13.0.4.10.54 - Device approval buttons work for non-admin managers

- "إلغاء الاعتماد" and the old-flow "موافقة وإصدار رمز" / "إعادة إصدار رمز التفعيل" wrote the
  admin-only hash fields (`groups=base.group_system`) as the current user, so a driver-app
  manager without Settings rights got an access error.
- After the existing manager-group check, those fields are now written with sudo.
