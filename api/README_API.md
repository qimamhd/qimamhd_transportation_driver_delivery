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
- `GET /api/driver/v1/current-batch?month=8&year=2026`
- `POST /api/driver/v1/complete-period`

كل المسارات ما عدا login تحتاج Header:

`Authorization: Bearer TOKEN`

## مثال تسجيل الدخول

```json
{
  "login": "0500000000",
  "pin": "1234",
  "device_name": "Samsung A55"
}
```

يمكن إرسال `password` بدل `pin`.

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
  "login": "0539959013",
  "pin": "1234",
  "device_name": "Postman Test"
}
```

This is a test endpoint only. It must not replace the production login route.
