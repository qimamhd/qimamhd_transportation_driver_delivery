# -*- coding: utf-8 -*-
"""Device activation by match code (pairing v2).

Flow:
1. /device-pairing/request: the driver's identity + password and a fresh
   Ed25519 public key. Creates a pending request tied to the driver and the
   driver's company, and returns a 6-digit match code (also shown in Odoo).
2. A manager compares the code on the phone with the one in Odoo and approves.
   Approval binds the device to the driver and revokes the old device.
3. /device-pairing/status: signed by the device key. Once approved, returns
   the one-time activation credential and approval id; the app then uses the
   existing challenge/verify and signed requests unchanged.

Enabled per company by `driver_app_device_pairing_v2` (off by default).
Every response carries `server_time` so the app can correct its clock.
"""
import base64
import binascii
import hashlib
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import urlsplit

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
except ImportError:
    Ed25519PublicKey = None
    InvalidSignature = Exception

from odoo import http, fields
from odoo.http import request

from .common import error, ok, read_json_body, request_payload_too_large
from ..models.device_approval import PAIRING_REQUEST_TTL

_NONCE_RE = r'^[A-Za-z0-9_-]{32,128}$'
_MAX_REQUESTS_PER_HOUR = 5
_STATUS_WINDOW_SECONDS = 90


def _server_time():
    return int(time.time())


def match_code_for(public_key, request_nonce):
    """6-digit code derived from the key and nonce; the app computes the same."""
    digest = hashlib.sha256(
        ('QIMAM-PAIRING-V1\n%s\n%s' % (public_key, request_nonce)).encode('utf-8')
    ).hexdigest()
    return '%06d' % (int(digest, 16) % 1000000)


def _decode_key(public_key):
    key_bytes = base64.urlsafe_b64decode(public_key + '=' * (-len(public_key) % 4))
    if len(key_bytes) != 32:
        raise ValueError('Invalid public key length')
    return Ed25519PublicKey.from_public_bytes(key_bytes)


class DriverDevicePairingAPI(http.Controller):

    @staticmethod
    def _authenticate_password(identification_id, password):
        """Same rules as /login: generic error, 5 failures lock 15 minutes."""
        if (not identification_id or password in (None, '')
                or len(identification_id) > 64 or len(str(password)) > 256):
            return None, error('INVALID_CREDENTIALS', 'بيانات الدخول غير صحيحة.', status=401)
        drivers = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification_id),
            ('driver_emp', '=', True),
            ('app_access_enabled', '=', True),
        ], limit=2)
        if len(drivers) != 1:
            return None, error('INVALID_CREDENTIALS', 'بيانات الدخول غير صحيحة.', status=401)
        driver = drivers[0]
        now = fields.Datetime.now()
        if driver.app_locked_until and driver.app_locked_until > now:
            return None, error('LOGIN_LOCKED', 'تم إيقاف محاولات الدخول مؤقتًا. حاول لاحقًا.', status=423)
        if not driver.verify_app_password(password):
            failed = (driver.app_failed_attempts or 0) + 1
            vals = {'app_failed_attempts': failed}
            if failed >= 5:
                vals['app_locked_until'] = now + timedelta(minutes=15)
            driver.sudo().write(vals)
            return None, error('INVALID_CREDENTIALS', 'بيانات الدخول غير صحيحة.', status=401)
        driver.sudo().write({'app_failed_attempts': 0, 'app_locked_until': False})
        return driver, None

    @staticmethod
    def _server_origin():
        parts = urlsplit(request.httprequest.host_url or '')
        host = (parts.hostname or '').lower()
        return '%s://%s%s' % (parts.scheme or 'https', host, (':%s' % parts.port) if parts.port else '')

    @http.route('/api/driver/v1/device-pairing/request', type='json', auth='public', methods=['POST'], csrf=False)
    def pairing_request(self, **kwargs):
        if request_payload_too_large(8192):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        if Ed25519PublicKey is None:
            return error('CRYPTO_UNAVAILABLE', 'خدمة التوقيع غير متاحة.', status=503)
        data = read_json_body()
        driver, response = self._authenticate_password(
            str(data.get('identification_id') or '').strip(), data.get('password'))
        if response:
            return response
        company = driver.company_id
        if not company or not company.driver_app_device_pairing_v2:
            return error('PAIRING_DISABLED', 'تفعيل الجهاز برمز المطابقة غير مفعّل لهذه الشركة.', status=403)

        device_id = str(data.get('device_id') or '').strip()
        device_name = str(data.get('device_name') or '').strip()[:128]
        public_key = str(data.get('public_key') or '').strip()
        nonce = str(data.get('request_nonce') or '').strip()
        if not (8 <= len(device_id) <= 128 and 32 <= len(public_key) <= 128
                and re.match(_NONCE_RE, nonce)):
            return error('INVALID_REQUEST', 'بيانات طلب التفعيل غير صالحة.')
        try:
            _decode_key(public_key)
        except (ValueError, binascii.Error):
            return error('INVALID_PUBLIC_KEY', 'المفتاح العام غير صالح.')

        model = request.env['trnsp.driver.device.approval'].sudo()
        now = fields.Datetime.now()
        recent = model.search_count([
            ('employee_id', '=', driver.id), ('flow', '=', 'pairing'),
            ('create_date', '>=', fields.Datetime.to_string(now - timedelta(hours=1))),
        ])
        if recent >= _MAX_REQUESTS_PER_HOUR:
            return error('RATE_LIMITED', 'طلبات تفعيل كثيرة. حاول بعد ساعة أو تواصل مع المسؤول.', status=429)
        if model.search_count([('request_nonce', '=', nonce)]):
            return error('DUPLICATE_REQUEST', 'الطلب مستخدم مسبقًا.', status=409)

        # Only the latest request of a driver stays pending.
        older = model.search([('employee_id', '=', driver.id), ('flow', '=', 'pairing'),
                              ('state', '=', 'pending')])
        if older:
            older.write({'state': 'rejected', 'reviewed_at': now})

        code = match_code_for(public_key, nonce)
        model.create({
            'name': 'طلب تفعيل: %s' % driver.name,
            'flow': 'pairing',
            'employee_id': driver.id,
            'company_id': company.id,
            'device_id': device_id,
            'device_name': device_name,
            'database_name': request.db,
            'server_origin': self._server_origin(),
            'public_key': public_key,
            'request_nonce': nonce,
            'match_code': code,
        })
        return ok({
            'state': 'pending',
            'match_code': code,
            'expires_in_seconds': int(PAIRING_REQUEST_TTL.total_seconds()),
            'server_time': _server_time(),
        })

    @http.route('/api/driver/v1/device-pairing/status', type='json', auth='public', methods=['POST'], csrf=False)
    def pairing_status(self, **kwargs):
        """Signed message: QIMAM-PAIRING-STATUS\\n<db>\\n<request_nonce>\\n<timestamp>\\n<nonce>"""
        if request_payload_too_large(4096):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        if Ed25519PublicKey is None:
            return error('CRYPTO_UNAVAILABLE', 'خدمة التوقيع غير متاحة.', status=503)
        data = read_json_body()
        request_nonce = str(data.get('request_nonce') or '').strip()
        device_id = str(data.get('device_id') or '').strip()
        timestamp = data.get('timestamp')
        nonce = str(data.get('nonce') or '').strip()
        signature = str(data.get('signature') or '').strip()
        if (not re.match(_NONCE_RE, request_nonce) or not re.match(_NONCE_RE, nonce)
                or not isinstance(timestamp, int) or not 8 <= len(device_id) <= 128
                or not re.fullmatch(r'[A-Za-z0-9_-]{80,100}={0,2}', signature)):
            return error('INVALID_REQUEST', 'طلب غير صالح.')
        server_time = _server_time()
        if abs(server_time - timestamp) > _STATUS_WINDOW_SECONDS:
            return error('DEVICE_PROOF_EXPIRED', 'ساعة الجهاز غير مضبوطة.', status=403,
                         details={'server_time': server_time})
        model = request.env['trnsp.driver.device.approval'].sudo()
        rec = model.search([('request_nonce', '=', request_nonce), ('flow', '=', 'pairing')], limit=1)
        if not rec or rec.device_id != device_id or rec.database_name != request.db:
            return error('NOT_FOUND', 'الطلب غير موجود.', status=404)
        try:
            sig = base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4))
            message = ('QIMAM-PAIRING-STATUS\n%s\n%s\n%s\n%s' % (
                request.db, request_nonce, timestamp, nonce)).encode('utf-8')
            _decode_key(rec.public_key).verify(sig, message)
        except (ValueError, binascii.Error, InvalidSignature):
            return error('INVALID_PROOF', 'إثبات الجهاز غير صالح.', status=401)
        from psycopg2 import IntegrityError
        try:
            with request.env.cr.savepoint():
                request.env['trnsp.driver.device.proof.nonce'].sudo().create({
                    'approval_id': rec.id, 'nonce': nonce,
                })
        except IntegrityError:
            return error('DEVICE_PROOF_REPLAY', 'تم استخدام هذا الإثبات مسبقًا.', status=403)

        request.env.cr.execute('SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE', (rec.id,))
        rec.invalidate_cache()
        result = {'state': rec.state, 'server_time': server_time}
        if rec.state == 'pending' and fields.Datetime.to_datetime(rec.create_date) < fields.Datetime.now() - PAIRING_REQUEST_TTL:
            result['state'] = 'expired'
        elif rec.state == 'approved':
            result['approval_id'] = rec.id
            if not rec.activation_used_at:
                credential = secrets.token_urlsafe(48)
                rec.write({
                    'activation_used_at': fields.Datetime.now(),
                    'credential_hash': hashlib.sha256(credential.encode('utf-8')).hexdigest(),
                })
                result['activation_credential'] = credential
            else:
                result['already_activated'] = True
        return ok(result)
