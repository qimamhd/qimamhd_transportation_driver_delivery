# -*- coding: utf-8 -*-

import hashlib
import base64
import binascii
import hmac
import re
import time

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
except ImportError:
    Ed25519PublicKey = None
    InvalidSignature = Exception
import json
from datetime import datetime

from odoo.http import request
from werkzeug.wrappers import Response


def _is_json_request():
    # Odoo 13 chooses JsonRequest from Content-Type before matching the route.
    # POST endpoints therefore use type='json'. In that mode controller methods
    # must return Python data, not a Werkzeug Response.
    return request.httprequest.mimetype == 'application/json'


def json_response(data, status=200):
    if _is_json_request():
        # Odoo's JsonRequest will wrap this value in its JSON-RPC response.
        # Keep the business/API status in the payload as HTTP status codes are
        # not propagated by Odoo's type='json' dispatcher.
        if isinstance(data, dict):
            data.setdefault('http_status', status)
        return data
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
    # For Odoo type='json', clients send JSON-RPC:
    # {"jsonrpc":"2.0","params":{...}}. Odoo exposes params to the
    # controller, while request.jsonrequest keeps the complete request.
    data = getattr(request, 'jsonrequest', None)
    if isinstance(data, dict):
        params = data.get('params')
        if isinstance(params, dict):
            return params
        return data
    data = request.httprequest.get_json(silent=True)
    return data if isinstance(data, dict) else {}



def request_payload_too_large(max_bytes):
    """Best-effort controller-side payload guard; Nginx remains authoritative."""
    raw = request.httprequest.headers.get('Content-Length')
    if not raw:
        return False
    try:
        return int(raw) > int(max_bytes)
    except (TypeError, ValueError):
        return True

def bearer_token():
    header = request.httprequest.headers.get('Authorization', '') or ''
    # Generated tokens are short. Bound the header value before hashing/searching.
    if len(header) > 512:
        return False
    parts = header.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        token = parts[1].strip()
        if 20 <= len(token) <= 256:
            return token
    return False


def token_hash(token):
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def require_signed_device_request(driver, bearer=''):
    """Opt-in Ed25519 proof for each protected request; fail closed when enabled.

    Signed UTF-8 message is the newline-delimited string:
    QIMAM-REQUEST-V2, database, approval_id, timestamp, nonce, method,
    path, raw query string, sha256(raw request body), sha256(bearer token or empty string).
    Nonce is recorded with a database uniqueness constraint before returning.
    """
    company = driver.company_id
    if not company or not company.driver_app_device_proof_required:
        return None
    if Ed25519PublicKey is None:
        return error('DEVICE_PROOF_UNAVAILABLE', 'التحقق الأمني غير متاح.', status=503)
    headers = request.httprequest.headers
    approval_text = headers.get('X-Qimam-Approval', '')
    timestamp_text = headers.get('X-Qimam-Timestamp', '')
    nonce = headers.get('X-Qimam-Nonce', '')
    signature = headers.get('X-Qimam-Signature', '')
    if (not re.fullmatch(r'[1-9][0-9]{0,12}', approval_text)
            or not re.fullmatch(r'[0-9]{10}', timestamp_text)
            or not re.fullmatch(r'[A-Za-z0-9_-]{32,96}', nonce)
            or not re.fullmatch(r'[A-Za-z0-9_-]{80,100}={0,2}', signature)):
        return error('DEVICE_PROOF_REQUIRED', 'يلزم إثبات اعتماد الجهاز.', status=403)
    if abs(int(time.time()) - int(timestamp_text)) > 90:
        return error('DEVICE_PROOF_EXPIRED', 'انتهت صلاحية إثبات الجهاز.', status=403)
    approval = request.env['trnsp.driver.device.approval'].sudo().browse(int(approval_text)).exists()
    if (not approval or approval.state != 'approved' or not approval.activation_used_at
            or not approval.credential_hash or approval.database_name != request.db
            or approval.company_id.id != company.id
            or not driver.app_device_id or approval.device_id != driver.app_device_id):
        return error('DEVICE_NOT_APPROVED', 'الجهاز غير معتمد.', status=403)
    body = request.httprequest.get_data(cache=True)
    if len(body) > 2 * 1024 * 1024:
        return error('PAYLOAD_TOO_LARGE', 'حجم الطلب أكبر من المسموح.', status=413)
    method = request.httprequest.method.upper()
    path = request.httprequest.path
    message = '\n'.join((
        'QIMAM-REQUEST-V2', request.db, approval_text, timestamp_text, nonce,
        method, path, request.httprequest.query_string.decode('latin-1'), hashlib.sha256(body).hexdigest(),
        hashlib.sha256((bearer or '').encode('utf-8')).hexdigest(),
    )).encode('utf-8')
    try:
        key = base64.urlsafe_b64decode(approval.public_key + '=' * (-len(approval.public_key) % 4))
        sig = base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4))
        if len(key) != 32 or len(sig) != 64:
            raise ValueError('Invalid key/signature size')
        Ed25519PublicKey.from_public_bytes(key).verify(sig, message)
    except (ValueError, binascii.Error, InvalidSignature):
        return error('INVALID_DEVICE_PROOF', 'توقيع الجهاز غير صحيح.', status=403)
    # Atomic replay defense: unique nonce per approval, independent of workers.
    # Use a savepoint so a collision does not abort the outer transaction.
    from psycopg2 import IntegrityError
    try:
        with request.env.cr.savepoint():
            request.env['trnsp.driver.device.proof.nonce'].sudo().create({
                'approval_id': approval.id, 'nonce': nonce,
            })
    except IntegrityError:
        return error('DEVICE_PROOF_REPLAY', 'تم استخدام هذا الإثبات مسبقًا.', status=403)
    return None


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
    proof_error = require_signed_device_request(driver, token)
    if proof_error:
        return None, proof_error
    if not driver or not driver.app_access_enabled or not driver.driver_emp:
        session.sudo().write({'revoked': True})
        return None, error(
            'APP_ACCESS_DISABLED',
            'دخول التطبيق غير مفعل لهذا السائق.',
            status=403,
        )

    # Device binding is a backend guard and is intentionally independent from
    # GPS/delivery logic. Once enabled, legacy/unbound sessions are invalidated
    # and the driver must perform one password login from the approved device.
    company = driver.company_id.sudo() if driver.company_id else False
    if company and company.driver_app_single_device:
        bound_device_id = (driver.app_device_id or '').strip()
        session_device_id = (session.device_id or '').strip()
        if not bound_device_id:
            session.sudo().write({'revoked': True})
            return None, error(
                'DEVICE_REBIND_REQUIRED',
                'يلزم تسجيل الدخول بكلمة المرور لاعتماد هذا الجهاز.',
                status=401,
            )
        if not session_device_id or session_device_id != bound_device_id:
            session.sudo().write({'revoked': True})
            return None, error(
                'DEVICE_SESSION_MISMATCH',
                'جلسة التطبيق لا تخص الجهاز المعتمد لهذا السائق. سجل الدخول من الجهاز المعتمد.',
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
