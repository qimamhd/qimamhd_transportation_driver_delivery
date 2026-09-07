# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request

from .common import (
    authenticate_driver,
    error,
    ok,
    read_json_body,
    bearer_token,
    request_payload_too_large,
)


class DriverAppAuthAPI(http.Controller):

    @http.route(
        '/api/driver/v1/login',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def login(self, **kwargs):
        if request_payload_too_large(16 * 1024):
            return error(
                'PAYLOAD_TOO_LARGE',
                'حجم الطلب أكبر من المسموح.',
                status=413,
            )

        data = read_json_body()
        identification_id = str(data.get('identification_id') or '').strip()
        password = data.get('password')
        device_name = str(data.get('device_name') or '').strip()[:128]

        if not identification_id:
            return error('IDENTIFICATION_REQUIRED', 'رقم الهوية مطلوب.')
        if password in (None, ''):
            return error(
                'PASSWORD_REQUIRED',
                'كلمة المرور مطلوبة.'
            )

        # Defensive bounds: avoid oversized input reaching ORM/password hashing.
        # Invalid bounds deliberately return the same generic credential response.
        if len(identification_id) > 64 or len(str(password)) > 256:
            return error(
                'INVALID_CREDENTIALS',
                'بيانات الدخول غير صحيحة.',
                status=401,
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

        try:
            token, session = request.env['trnsp.driver.app.session'].sudo().create_session(
                driver,
                device_name=device_name,
            )
        except Exception:
            request.env.cr.rollback()
            return error(
                'LOGIN_FAILED',
                'تعذر إنشاء جلسة التطبيق. حاول مرة أخرى.',
                status=500,
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

    @http.route(
        '/api/driver/v1/biometric/enroll',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def biometric_enroll(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, _session = auth
        if not driver.biometric_allowed:
            return error(
                'BIOMETRIC_NOT_ALLOWED',
                'الدخول بالبصمة غير مسموح لهذا الحساب.',
                status=403,
            )

        data = read_json_body()
        device_id = str(data.get('device_id') or '').strip()
        device_name = str(data.get('device_name') or '').strip()[:128]
        if not device_id or len(device_id) > 128:
            return error('DEVICE_ID_REQUIRED', 'معرف الجهاز غير صالح.', status=400)

        try:
            token, credential = request.env[
                'trnsp.driver.biometric.credential'
            ].sudo().create_credential(
                driver,
                device_id=device_id,
                device_name=device_name,
            )
        except Exception:
            request.env.cr.rollback()
            return error(
                'BIOMETRIC_ENROLL_FAILED',
                'تعذر تفعيل الدخول بالبصمة حاليًا.',
                status=500,
            )

        return ok({
            'credential': token,
            'expires_at': credential.expires_at,
            'device_id': credential.device_id,
        })

    @http.route(
        '/api/driver/v1/biometric/login',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def biometric_login(self, **kwargs):
        if request_payload_too_large(16 * 1024):
            return error(
                'PAYLOAD_TOO_LARGE',
                'حجم الطلب أكبر من المسموح.',
                status=413,
            )
        data = read_json_body()
        credential_token = str(data.get('credential') or '').strip()
        device_id = str(data.get('device_id') or '').strip()
        device_name = str(data.get('device_name') or '').strip()[:128]
        if not credential_token or not device_id:
            return error(
                'BIOMETRIC_CREDENTIAL_REQUIRED',
                'اعتماد الدخول بالبصمة غير متوفر.',
                status=401,
            )
        if len(credential_token) > 256 or len(device_id) > 128:
            return error(
                'INVALID_BIOMETRIC_CREDENTIAL',
                'اعتماد الدخول بالبصمة غير صالح أو منتهي.',
                status=401,
            )

        credential = request.env[
            'trnsp.driver.biometric.credential'
        ].sudo().find_active(credential_token)
        if not credential or credential.device_id != device_id:
            return error(
                'INVALID_BIOMETRIC_CREDENTIAL',
                'اعتماد الدخول بالبصمة غير صالح أو منتهي.',
                status=401,
            )

        driver = credential.employee_id.sudo()
        if (
            not driver
            or not driver.driver_emp
            or not driver.app_access_enabled
            or not driver.biometric_allowed
        ):
            credential.sudo().write({'revoked': True})
            return error(
                'BIOMETRIC_NOT_ALLOWED',
                'الدخول بالبصمة غير مسموح لهذا الحساب.',
                status=403,
            )

        try:
            token, session = request.env[
                'trnsp.driver.app.session'
            ].sudo().create_session(driver, device_name=device_name)
        except Exception:
            request.env.cr.rollback()
            return error(
                'LOGIN_FAILED',
                'تعذر إنشاء جلسة التطبيق. حاول مرة أخرى.',
                status=500,
            )

        credential.sudo().write({'last_used_at': fields.Datetime.now()})
        driver.sudo().write({'app_last_login': fields.Datetime.now()})
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
        '/api/driver/v1/biometric/revoke',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def biometric_revoke(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, _session = auth
        data = read_json_body()
        device_id = str(data.get('device_id') or '').strip()
        if not device_id or len(device_id) > 128:
            return error('DEVICE_ID_REQUIRED', 'معرف الجهاز غير صالح.', status=400)

        credentials = request.env[
            'trnsp.driver.biometric.credential'
        ].sudo().search([
            ('employee_id', '=', driver.id),
            ('device_id', '=', device_id),
            ('revoked', '=', False),
        ])
        if credentials:
            credentials.write({'revoked': True})
        return ok(message='تم تعطيل الدخول بالبصمة على هذا الجهاز.')

