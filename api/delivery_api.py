# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError

from .common import (
    authenticate_driver,
    company_domain,
    driver_branch_id,
    error,
    float_value,
    int_value,
    ok,
    read_json_body,
)


class DriverAppDeliveryAPI(http.Controller):

    def _get_or_create_batch(self, driver, request_date):
        month = '%02d' % request_date.month
        year = request_date.year
        company = driver.company_id

        Batch = request.env['trnsp.store.driver.request.batch'].sudo()
        batch = Batch.search([
            ('driver_id', '=', driver.id),
            ('month_name', '=', month),
            ('year', '=', year),
            ('company_id', '=', company.id),
        ], limit=1)

        if batch:
            if batch.state != 'draft':
                return False, error(
                    'PERIOD_LOCKED',
                    'ملف هذا الشهر غير مفتوح لاستقبال توصيلات جديدة.',
                    status=409,
                    details={
                        'batch_id': batch.id,
                        'batch_name': batch.name,
                        'state': batch.state,
                    }
                )
            return batch, None

        branch_id = driver_branch_id(driver)
        if not branch_id:
            return False, error(
                'BRANCH_NOT_CONFIGURED',
                'لا يوجد فرع مرتبط بالسائق. اربط السائق/مستخدمه بفرع قبل استخدام التطبيق.',
                status=409,
            )

        batch = Batch.create({
            'driver_id': driver.id,
            'month_name': month,
            'year': year,
            'company_id': company.id,
            'branch_id': branch_id,
        })
        return batch, None

    @http.route(
        '/api/driver/v1/deliveries',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def create_delivery(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth
        data = read_json_body()

        mobile_uuid = (data.get('uuid') or '').strip()
        if not mobile_uuid:
            return error('UUID_REQUIRED', 'uuid مطلوب لكل توصيلة.')

        # Idempotency: repeated mobile sends return the original row, not a duplicate.
        existing = request.env['trnsp.store.driver.request.line'].sudo().search([
            ('mobile_uuid', '=', mobile_uuid),
        ], limit=1)
        if existing:
            if existing.driver_id.id != driver.id:
                return error(
                    'UUID_CONFLICT',
                    'uuid مستخدم في توصيلة أخرى.',
                    status=409,
                )
            return ok({
                'id': existing.id,
                'uuid': existing.mobile_uuid,
                'batch_id': existing.batch_id.id,
                'batch_name': existing.batch_id.name,
                'gps_valid': bool(existing.gps_valid),
                'gps_distance': existing.gps_distance,
                'duplicate': True,
            }, message='التوصيلة مسجلة مسبقًا.')

        required = ['source_id', 'destination_id', 'car_id', 'date', 'time', 'latitude', 'longitude']
        missing = [name for name in required if data.get(name) in (None, '')]
        if missing:
            return error(
                'MISSING_FIELDS',
                'حقول مطلوبة غير مرسلة.',
                details={'fields': missing},
            )

        try:
            source_id = int_value(data.get('source_id'), 'source_id')
            destination_id = int_value(data.get('destination_id'), 'destination_id')
            car_id = int_value(data.get('car_id'), 'car_id')
            latitude = float_value(data.get('latitude'), 'latitude')
            longitude = float_value(data.get('longitude'), 'longitude')
            request_date = fields.Date.from_string(data.get('date'))
        except (ValueError, TypeError) as exc:
            return error('INVALID_INPUT', str(exc))

        if not request_date:
            return error('INVALID_DATE', 'صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.')
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return error('INVALID_GPS', 'إحداثيات السائق خارج النطاق الصحيح.')

        Product = request.env['product.product'].sudo()
        car_domain = [('id', '=', car_id), ('car_flag', '=', True)]
        car_domain += company_domain(Product, driver.company_id)
        car = Product.search(car_domain, limit=1)
        if not car:
            return error('INVALID_CAR', 'السيارة المحددة غير متاحة.', status=404)

        Pricing = request.env['trnsp.store.pricing'].sudo()
        pricing_domain = [('source_path_id', '=', source_id)]
        pricing_domain += company_domain(Pricing, driver.company_id)
        pricing_headers = Pricing.search(pricing_domain)
        if not pricing_headers:
            return error(
                'SOURCE_NOT_PRICED',
                'المصدر غير موجود في شاشة التسعيرات.',
                status=404,
            )

        pricing_line = pricing_headers.mapped('pricing_lines').filtered(
            lambda line: line.destination_path_id.id == destination_id
        )[:1]
        if not pricing_line:
            return error(
                'DESTINATION_NOT_ALLOWED',
                'الوجهة غير مرتبطة بالمصدر المحدد في شاشة التسعيرات.',
                status=409,
            )

        batch, batch_error = self._get_or_create_batch(driver, request_date)
        if batch_error:
            return batch_error

        try:
            line = request.env['trnsp.store.driver.request.line'].sudo().create({
                'batch_id': batch.id,
                'mobile_uuid': mobile_uuid,
                'request_date': request_date,
                'request_time': data.get('time'),
                'product_car_id': car.id,
                'source_path_id': source_id,
                'destination_path_id': destination_id,
                'driver_latitude': latitude,
                'driver_longitude': longitude,
                'notes': (data.get('notes') or '').strip()[:255],
                'server_received_at': fields.Datetime.now(),
            })
        except ValidationError as exc:
            return error('VALIDATION_ERROR', str(exc), status=409)
        except Exception:
            # Keep technical internals out of the public API response.
            request.env.cr.rollback()
            return error(
                'CREATE_FAILED',
                'تعذر حفظ التوصيلة. راجع إعدادات السائق والمسار.',
                status=500,
            )

        return ok({
            'id': line.id,
            'uuid': line.mobile_uuid,
            'batch_id': batch.id,
            'batch_name': batch.name,
            'gps_valid': bool(line.gps_valid),
            'gps_distance': line.gps_distance,
            'allowed_radius': line.allowed_radius,
            'review_state': line.review_state,
            'duplicate': False,
        }, message='تم تسجيل التوصيلة.', status=201)

    @http.route(
        '/api/driver/v1/current-batch',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def current_batch(self, month=None, year=None, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth

        today = fields.Date.today()
        try:
            month = int(month or today.month)
            year = int(year or today.year)
        except (TypeError, ValueError):
            return error('INVALID_PERIOD', 'الشهر أو السنة غير صحيح.')
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            return error('INVALID_PERIOD', 'الشهر أو السنة غير صحيح.')

        batch = request.env['trnsp.store.driver.request.batch'].sudo().search([
            ('driver_id', '=', driver.id),
            ('month_name', '=', '%02d' % month),
            ('year', '=', year),
            ('company_id', '=', driver.company_id.id),
        ], limit=1)

        if not batch:
            return ok(None, message='لا يوجد ملف لهذا الشهر.')

        return ok({
            'id': batch.id,
            'name': batch.name,
            'month': batch.month_name,
            'year': batch.year,
            'state': batch.state,
            'line_count': batch.line_count,
            'gps_valid_count': batch.gps_valid_count,
            'gps_invalid_count': batch.gps_invalid_count,
            'pending_count': batch.pending_count,
            'accepted_count': batch.accepted_count,
            'rejected_count': batch.rejected_count,
        })

    @http.route(
        '/api/driver/v1/complete-period',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def complete_period(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth
        data = read_json_body()

        today = fields.Date.today()
        try:
            month = int(data.get('month') or today.month)
            year = int(data.get('year') or today.year)
        except (TypeError, ValueError):
            return error('INVALID_PERIOD', 'الشهر أو السنة غير صحيح.')
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            return error('INVALID_PERIOD', 'الشهر أو السنة غير صحيح.')

        batch = request.env['trnsp.store.driver.request.batch'].sudo().search([
            ('driver_id', '=', driver.id),
            ('month_name', '=', '%02d' % month),
            ('year', '=', year),
            ('company_id', '=', driver.company_id.id),
        ], limit=1)
        if not batch:
            return error('BATCH_NOT_FOUND', 'لا يوجد ملف لهذا الشهر.', status=404)
        if batch.state != 'draft':
            return error(
                'PERIOD_LOCKED',
                'ملف الشهر غير مفتوح.',
                status=409,
                details={'state': batch.state},
            )

        try:
            batch.action_mark_done()
        except ValidationError as exc:
            return error('VALIDATION_ERROR', str(exc), status=409)

        return ok({
            'batch_id': batch.id,
            'batch_name': batch.name,
            'state': batch.state,
        }, message='تم إكمال ملف الشهر وإقفاله عن استقبال توصيلات جديدة.')
