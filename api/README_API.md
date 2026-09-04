# Driver App API - Odoo 13

هذا المجلد مستقل عن شاشات Odoo لتسهيل فهم الـ API وصيانته.

## الملفات

- `common.py`: الردود JSON، Bearer Token، التحقق من الجلسة، وتحويل القيم.
- `auth_api.py`: تسجيل الدخول، تسجيل الخروج، وبيانات السائق.
- `master_data_api.py`: السيارات، المصادر، والوجهات المسموحة من شاشة التسعيرات.
- `delivery_api.py`: إرسال التوصيلة، الملف الشهري الحالي، وإكمال ملف الشهر.
- `models/app_session.py`: تخزين جلسات التطبيق. لا يتم تخزين الـ Token الخام؛ يخزن SHA-256 فقط.

## المسارات

- `POST /api/driver/v1/login`
- `POST /api/driver/v1/logout`
- `GET /api/driver/v1/profile`
- `GET /api/driver/v1/cars`
- `GET /api/driver/v1/sources`
- `GET /api/driver/v1/destinations?source_id=4`
- `POST /api/driver/v1/deliveries`
- `GET /api/driver/v1/delivery-periods`
- `GET /api/driver/v1/delivery-period-options` — returns only periods currently allowed by Odoo for new delivery submission.
- `GET /api/driver/v1/current-batch?month=8&year=2026`
- `POST /api/driver/v1/complete-period`

كل المسارات ما عدا login تحتاج Header:

`Authorization: Bearer TOKEN`

## مثال تسجيل الدخول

```json
{
  "identification_id": "1234567890",
  "password": "your-password",
  "device_name": "Samsung A55"
}
```

تسجيل الدخول يعتمد على `hr.employee.identification_id` كاسم مستخدم، وكلمة مرور التطبيق المخزنة بشكل مشفّر.

## مثال تسجيل توصيلة

```json
{
  "uuid": "9c7df3a8-9808-4d9a-a6d8-3bf677975ead",
  "car_id": 15,
  "source_id": 4,
  "destination_id": 18,
  "date": "2026-08-29",
  "time": "13:42:16",
  "latitude": 21.543210,
  "longitude": 39.172540,
  "notes": "تم التسليم للمطعم"
}
```

السيرفر يعيد التحقق من أن المصدر موجود في `trnsp.store.pricing` وأن الوجهة موجودة في سطور تسعير نفس المصدر، ثم يحسب GPS من إعداد التسعير. تكرار نفس `uuid` لا ينشئ توصيلة ثانية.

## ملاحظات مهمة

- التطبيق لا يرسل نتيجة GPS؛ السيرفر يحسبها.
- التطبيق لا يرسل اسم السائق؛ السائق يؤخذ من الـ Token.
- الملف الشهري يتم إنشاؤه تلقائيًا عند أول توصيلة، بشرط وجود فرع مرتبط بالسائق أو بمستخدم السائق.
- إذا الملف الشهري لم يعد `draft` ترجع الخدمة `PERIOD_LOCKED`.
- جلسة التطبيق صالحة 30 يومًا، ويمكن إلغاؤها عند logout.


## TEST ONLY - login without changing dbfilter

POST `/api/driver/v1/login_test`

This route is fixed to database `almirabi_2025_test`.

```json
{
  "identification_id": "1234567890",
  "password": "your-password",
  "device_name": "Postman Test"
}
```

This is a test endpoint only. It must not replace the production login route.


## Odoo 13 JSON POST format (v13.0.4.0.3)

Odoo 13 selects the request dispatcher from `Content-Type` before route matching.
All production POST endpoints therefore use `type='json'` and must be called with
`Content-Type: application/json` using a JSON-RPC envelope. Example login:

```json
{
  "jsonrpc": "2.0",
  "params": {
    "identification_id": "1234567890",
    "password": "your-password",
    "device_name": "Postman Test"
  }
}
```

POST endpoints: `/login`, `/logout`, `/deliveries`, `/complete-period`.
GET endpoints remain normal HTTP GET endpoints and return plain JSON.
The temporary `/login_test` route remains `type='http'` for isolated test-database
diagnostics only and must be removed before production deployment.


## Connection health
- `GET /api/driver/v1/ping` - safe unauthenticated connection check for Qimam Route setup.
- The temporary `login_test` endpoint was removed in v13.0.4.2.0 and must not exist in production.

- `GET /api/driver/v1/branding` — public presentation-only company name/logo for the pre-login screen.

## Added in 13.0.4.7.0
- `POST /api/driver/v1/biometric/enroll` — create/rotate a persistent device biometric credential for the authenticated driver.
- `POST /api/driver/v1/biometric/login` — exchange the device biometric credential for a fresh normal app session after OS biometric verification on the mobile side.
- `POST /api/driver/v1/biometric/revoke` — revoke this driver's biometric credential for the supplied device.
- `GET /api/driver/v1/dashboard?year=2026` — lightweight grouped driver statistics; returns current year, previous-year comparison, monthly counts, and review-state totals.
