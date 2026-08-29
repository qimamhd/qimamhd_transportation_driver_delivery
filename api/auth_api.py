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
        type='http', auth='public', methods=['POST'], csrf=False
    )
    def login(self, **kwargs):
        data = read_json_body()
        login = (data.get('login') or '').strip()
        pin = data.get('pin')
        password = data.get('password')
        device_name = (data.get('device_name') or '').strip()[:128]

        if not login:
            return error('LOGIN_REQUIRED', 'اسم الدخول مطلوب.')
        if pin in (None, '') and password in (None, ''):
            return error(
                'CREDENTIAL_REQUIRED',
                'أرسل PIN أو كلمة المرور.'
            )

        driver = request.env['hr.employee'].sudo().search([
            ('app_login', '=', login),
            ('driver_emp', '=', True),
        ], limit=1)

        # Do not reveal whether the login exists.
        if not driver or not driver.app_access_enabled:
            return error(
                'INVALID_CREDENTIALS',
                'بيانات الدخول غير صحيحة.',
                status=401,
            )

        now = fields.Datetime.now()
        if driver.app_locked_until and driver.app_locked_until > now:
            return error(
                'LOGIN_LOCKED',
                'تم إيقاف محاولات الدخول مؤقتًا. حاول لاحقًا.',
                status=423,
            )

        valid = False
        if pin not in (None, ''):
            valid = driver.verify_app_pin(pin)
        elif password not in (None, ''):
            valid = driver.verify_app_password(password)

        if not valid:
            failed = (driver.app_failed_attempts or 0) + 1
            vals = {'app_failed_attempts': failed}
            if failed >= 5:
                vals.update({
                    'app_failed_attempts': 0,
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
                'login': driver.app_login,
                'company_id': driver.company_id.id if driver.company_id else False,
                'company_name': driver.company_id.name if driver.company_id else False,
                'biometric_allowed': bool(driver.biometric_allowed),
            },
        })

    @http.route(
        '/api/driver/v1/logout',
        type='http', auth='public', methods=['POST'], csrf=False
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
            'login': driver.app_login,
            'company_id': driver.company_id.id if driver.company_id else False,
            'company_name': driver.company_id.name if driver.company_id else False,
            'biometric_allowed': bool(driver.biometric_allowed),
            'session_expires_at': session.expires_at,
        })
