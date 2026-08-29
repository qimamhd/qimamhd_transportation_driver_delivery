# -*- coding: utf-8 -*-

import hashlib
import json
from datetime import datetime

from odoo.http import request
from werkzeug.wrappers import Response


def json_response(data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str)
    return Response(
        body,
        status=status,
        content_type='application/json; charset=utf-8',
    )


def ok(data=None, message=None, status=200):
    payload = {'ok': True}
    if message:
        payload['message'] = message
    if data is not None:
        payload['data'] = data
    return json_response(payload, status=status)


def error(code, message, status=400, details=None):
    payload = {
        'ok': False,
        'error': {
            'code': code,
            'message': message,
        },
    }
    if details is not None:
        payload['error']['details'] = details
    return json_response(payload, status=status)


def read_json_body():
    data = request.httprequest.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def bearer_token():
    header = request.httprequest.headers.get('Authorization', '') or ''
    parts = header.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1].strip()
    return False


def token_hash(token):
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def authenticate_driver():
    token = bearer_token()
    if not token:
        return None, error(
            'AUTH_REQUIRED',
            'يلزم إرسال Bearer token صالح.',
            status=401,
        )

    session = request.env['trnsp.driver.app.session'].sudo().search([
        ('token_hash', '=', token_hash(token)),
        ('revoked', '=', False),
    ], limit=1)

    if not session or session.is_expired():
        if session and not session.revoked:
            session.sudo().write({'revoked': True})
        return None, error(
            'INVALID_TOKEN',
            'جلسة التطبيق غير صالحة أو منتهية.',
            status=401,
        )

    driver = session.employee_id.sudo()
    if not driver or not driver.app_access_enabled or not driver.driver_emp:
        session.sudo().write({'revoked': True})
        return None, error(
            'APP_ACCESS_DISABLED',
            'دخول التطبيق غير مفعل لهذا السائق.',
            status=403,
        )

    session.sudo().write({'last_used_at': datetime.utcnow()})
    return (driver, session), None


def int_value(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError('%s يجب أن يكون رقمًا صحيحًا.' % field_name)


def float_value(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError('%s يجب أن يكون رقمًا.' % field_name)


def company_domain(model, company):
    if 'company_id' not in model._fields or not company:
        return []
    return ['|', ('company_id', '=', False), ('company_id', '=', company.id)]


def driver_branch_id(driver):
    # Prefer a branch explicitly linked to the employee when the base project has it.
    if 'branch_id' in driver._fields and driver.branch_id:
        return driver.branch_id.id

    if 'user_id' in driver._fields and driver.user_id:
        user = driver.user_id.sudo()
        if 'branch_id' in user._fields and user.branch_id:
            return user.branch_id.id

    return False
