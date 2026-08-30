# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import secrets

from odoo import http, fields
from odoo.http import request

from .common import (
    authenticate_driver,
    error,
    ok,
    read_json_body,
    bearer_token,
)


class DriverAppAuthAPI(http.Controller):

    @http.route(
        '/api/driver/v1/login',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def login(self, **kwargs):
        data = read_json_body()
        identification_id = (data.get('identification_id') or '').strip()
        password = data.get('password')
        device_name = (data.get('device_name') or '').strip()[:128]

        if not identification_id:
            return error('IDENTIFICATION_REQUIRED', 'رقم الهوية مطلوب.')
        if password in (None, ''):
            return error(
                'PASSWORD_REQUIRED',
                'كلمة المرور مطلوبة.'
            )

        drivers = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification_id),
            ('driver_emp', '=', True),
            ('app_access_enabled', '=', True),
        ], limit=2)

        # Do not reveal whether the identity is missing, disabled, or duplicated.
        # Duplicated enabled identities are rejected rather than authenticating
        # an arbitrary employee record.
        if len(drivers) != 1:
            return error(
                'INVALID_CREDENTIALS',
                'بيانات الدخول غير صحيحة.',
                status=401,
            )

        driver = drivers[0]
        now = fields.Datetime.now()
        if driver.app_locked_until and driver.app_locked_until > now:
            return error(
                'LOGIN_LOCKED',
                'تم إيقاف محاولات الدخول مؤقتًا. حاول لاحقًا.',
                status=423,
            )

        valid = driver.verify_app_password(password)

        if not valid:
            failed = (driver.app_failed_attempts or 0) + 1
            vals = {'app_failed_attempts': failed}
            if failed >= 5:
                vals.update({
                    # Keep the failed-attempt count visible while the account is
                    # locked. The manager unlock action (or a successful login
                    # after the lock expires) is responsible for resetting it.
                    'app_failed_attempts': failed,
                    'app_locked_until': now + timedelta(minutes=15),
                })
            driver.sudo().write(vals)
            return error(
                'INVALID_CREDENTIALS',
                'بيانات الدخول غير صحيحة.',
                status=401,
            )

        driver.sudo().write({
            'app_failed_attempts': 0,
            'app_locked_until': False,
            'app_last_login': now,
        })

        token, session = request.env['trnsp.driver.app.session'].sudo().create_session(
            driver,
            device_name=device_name,
        )

        return ok({
            'token': token,
            'token_type': 'Bearer',
            'expires_at': session.expires_at,
            'driver': {
                'id': driver.id,
                'name': driver.name,
                'identification_id': driver.identification_id,
                'company_id': driver.company_id.id if driver.company_id else False,
                'company_name': driver.company_id.name if driver.company_id else False,
                'biometric_allowed': bool(driver.biometric_allowed),
            },
        })

    @http.route(
        '/api/driver/v1/logout',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def logout(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth
        session.sudo().write({'revoked': True})
        return ok(message='تم تسجيل الخروج.')

    @http.route(
        '/api/driver/v1/profile',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def profile(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth
        return ok({
            'id': driver.id,
            'name': driver.name,
            'identification_id': driver.identification_id,
            'company_id': driver.company_id.id if driver.company_id else False,
            'company_name': driver.company_id.name if driver.company_id else False,
            'biometric_allowed': bool(driver.biometric_allowed),
            'session_expires_at': session.expires_at,
        })

class DriverLoginTestController(http.Controller):

    @http.route(
        '/api/driver/v1/login_test',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False
    )
    def driver_login_test(self, **kwargs):
        import json
        from odoo import api, registry, SUPERUSER_ID
        from odoo.http import request
        from werkzeug.wrappers import Response

        test_db = 'almirabi_2025_test'

        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except Exception:
            payload = {}

        identification_id = (payload.get('identification_id') or '').strip()
        password = str(payload.get('password') or '').strip()
        device_name = (payload.get('device_name') or '').strip()

        def respond(body, status):
            return Response(
                json.dumps(body, ensure_ascii=False),
                status=status,
                content_type='application/json; charset=utf-8'
            )

        if not identification_id or not password:
            return respond({
                'success': False,
                'code': 'MISSING_CREDENTIALS',
                'message': 'identification_id and password are required',
            }, 400)

        try:
            reg = registry(test_db)
            with reg.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                employees = env['hr.employee'].sudo().search([
                    ('app_access_enabled', '=', True),
                    ('driver_emp', '=', True),
                    ('identification_id', '=', identification_id),
                ], limit=2)

                if len(employees) != 1:
                    return respond({
                        'success': False,
                        'code': 'INVALID_CREDENTIALS',
                        'message': 'Invalid login or credentials',
                    }, 401)

                employee = employees[0]
                valid = employee.verify_app_password(password)
                if not valid:
                    return respond({
                        'success': False,
                        'code': 'INVALID_CREDENTIALS',
                        'message': 'Invalid login or credentials',
                    }, 401)

                return respond({
                    'success': True,
                    'test_mode': True,
                    'database': test_db,
                    'driver': {
                        'id': employee.id,
                        'name': employee.name,
                        'identification_id': employee.identification_id,
                    },
                    'device_name': device_name,
                    'message': 'TEST LOGIN OK',
                }, 200)

        except Exception as exc:
            return respond({
                'success': False,
                'code': 'TEST_LOGIN_ERROR',
                'message': str(exc),
            }, 500)

