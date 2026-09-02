# v13.0.4.6.0 - Manager GPS Exception Acceptance

## الهدف
إتاحة قبول استثنائي للتوصيلات خارج نطاق GPS بواسطة مدير طلبات تطبيق السائقين فقط، مع إبقاء حقيقة GPS كما هي وعدم تحويل `gps_valid` إلى صحيح.

## السلوك
- زر **قبول استثنائي** يظهر للمدير فقط على التوصيلة خارج النطاق أثناء حالة **قيد المراجعة**.
- يفتح معالج يفرض إدخال سبب القبول.
- تحفظ التوصيلة كمقبولة مع `gps_valid = False` و `gps_exception_approved = True`.
- تحفظ بيانات التدقيق: السبب، المدير، التاريخ والوقت.
- القبول الاستثنائي المؤكد يسمح باعتماد الملف والتحويل للحسبة مثل أي توصيلة مقبولة.
- القبول العادي لا يزال ممنوعاً للتوصيلات خارج النطاق.
- إعادة التوصيلة للمراجعة أو رفضها تمسح بيانات الاستثناء حتى لا تبقى موافقة قديمة فعالة.

## الملفات
- `models/store_driver_request.py`
- `models/exception_accept_wizard.py`
- `models/__init__.py`
- `views/store_driver_request_views.xml`
- `views/exception_accept_wizard_views.xml`
- `security/ir.model.access.csv`
- `__manifest__.py`
