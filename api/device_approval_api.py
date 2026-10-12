# -*- coding: utf-8 -*-
"""Device approval transport (stage 2). Enforcement is NOT enabled here."""
import hashlib
import base64
import binascii
import hmac
import re
import secrets
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


class DriverDeviceApprovalAPI(http.Controller):
    @staticmethod
    def _origin(value):
        if not isinstance(value, str) or len(value) > 250:
            return None
        try:
            parts = urlsplit(value.strip())
            if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
                return None
            return '%s://%s%s' % (parts.scheme, parts.hostname.lower(), (':%s' % parts.port) if parts.port else '')
        except (ValueError, AttributeError):
            return None

    @http.route('/api/driver/v1/device-approval/request', type='json', auth='public', methods=['POST'], csrf=False)
    def create_request(self, **kwargs):
        if request_payload_too_large(8192):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        data = read_json_body()
        device_id = str(data.get('device_id') or '').strip()
        device_name = str(data.get('device_name') or '').strip()[:128]
        database_name = str(data.get('database_name') or '').strip()
        origin = self._origin(data.get('server_origin'))
        public_key = str(data.get('public_key') or '').strip()
        nonce = str(data.get('request_nonce') or '').strip()
        if not (8 <= len(device_id) <= 128 and re.match(r'^[a-zA-Z0-9_.-]{1,80}$', database_name)
                and database_name == request.db and origin and 32 <= len(public_key) <= 4096
                and re.match(r'^[a-zA-Z0-9_-]{32,128}$', nonce)):
            return error('INVALID_REQUEST', 'بيانات طلب التفعيل غير صالحة.')
        # Accept only a real Ed25519 public key, encoded as base64url (32 bytes).
        if Ed25519PublicKey is None:
            return error('CRYPTO_UNAVAILABLE', 'خدمة التوقيع غير متاحة.', status=503)
        try:
            key_bytes = base64.urlsafe_b64decode(public_key + '=' * (-len(public_key) % 4))
            if len(key_bytes) != 32:
                raise ValueError('Invalid public key length')
            Ed25519PublicKey.from_public_bytes(key_bytes)
        except (ValueError, binascii.Error):
            return error('INVALID_PUBLIC_KEY', 'المفتاح العام غير صالح.')
        # Prevent trivial abuse of the public endpoint; stronger ingress throttling
        # is recommended before rollout. Never expose other requests' IDs.
        model = request.env['trnsp.driver.device.approval'].sudo()
        now = fields.Datetime.now()
        recent = fields.Datetime.to_string(now - timedelta(hours=1))
        if model.search_count([('device_id', '=', device_id), ('create_date', '>=', recent)]) >= 3:
            return error('RATE_LIMITED', 'طلبات كثيرة لهذا الجهاز؛ حاول لاحقًا.', status=429)
        if model.search_count([('request_nonce', '=', nonce)]):
            return error('DUPLICATE_REQUEST', 'الطلب مستخدم مسبقًا.', status=409)
        # Company cannot be securely inferred from an unauthenticated request.
        # Assigning a company here would allow untrusted users to target it.
        # Administrative review must validate the selected company manually.
        company = request.env['res.company'].sudo().search([], order='id', limit=1)
        if not company:
            return error('CONFIGURATION_ERROR', 'لا توجد شركة مهيأة.', status=503)
        record = model.create({
            'company_id': company.id,
            'device_id': device_id,
            'device_name': device_name,
            'database_name': database_name,
            'server_origin': origin,
            'public_key': public_key,
            'request_nonce': nonce,
        })
        return ok({'request_id': record.id, 'state': 'pending'})

    @http.route('/api/driver/v1/device-approval/status', type='json', auth='public', methods=['POST'], csrf=False)
    def status(self, **kwargs):
        data = read_json_body()
        nonce = str(data.get('request_nonce') or '').strip()
        if not re.match(r'^[a-zA-Z0-9_-]{32,128}$', nonce):
            return error('INVALID_REQUEST', 'طلب غير صالح.')
        rec = request.env['trnsp.driver.device.approval'].sudo().search([('request_nonce', '=', nonce)], limit=1)
        if not rec:
            return error('NOT_FOUND', 'الطلب غير موجود.', status=404)
        return ok({'state': rec.state})

    @http.route('/api/driver/v1/device-approval/activate', type='json', auth='public', methods=['POST'], csrf=False)
    def activate(self, **kwargs):
        if request_payload_too_large(4096):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        data = read_json_body()
        nonce = str(data.get('request_nonce') or '').strip()
        code = str(data.get('activation_code') or '').strip()
        device_id = str(data.get('device_id') or '').strip()
        if not re.match(r'^[a-zA-Z0-9_-]{32,128}$', nonce) or len(code) > 128 or len(device_id) > 128:
            return error('INVALID_ACTIVATION', 'بيانات التفعيل غير صحيحة.', status=401)
        model = request.env['trnsp.driver.device.approval'].sudo()
        rec = model.search([('request_nonce', '=', nonce)], limit=1)
        if not rec:
            return error('INVALID_ACTIVATION', 'بيانات التفعيل غير صحيحة.', status=401)
        # Serialize competing attempts to prevent concurrent reuse of one-time codes.
        request.env.cr.execute('SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE', (rec.id,))
        rec.invalidate_cache()
        if rec.state != 'approved' or rec.activation_used_at or rec.failed_attempts >= 5 or not rec.activation_hash or not rec.activation_expires_at or fields.Datetime.to_datetime(rec.activation_expires_at) < fields.Datetime.to_datetime(fields.Datetime.now()) or rec.device_id != device_id:
            return error('INVALID_ACTIVATION', 'الرمز غير صالح أو منتهي.', status=401)
        digest = hashlib.sha256(code.encode('utf-8')).hexdigest()
        if not hmac.compare_digest(digest, rec.activation_hash):
            rec.write({'failed_attempts': rec.failed_attempts + 1})
            return error('INVALID_ACTIVATION', 'الرمز غير صالح أو منتهي.', status=401)
        credential = secrets.token_urlsafe(48)
        rec.write({
            'activation_used_at': fields.Datetime.now(),
            'activation_hash': False,
            'credential_hash': hashlib.sha256(credential.encode('utf-8')).hexdigest(),
        })
        return ok({'activation_credential': credential, 'approval_id': rec.id})

    @http.route('/api/driver/v1/device-approval/challenge', type='json', auth='public', methods=['POST'], csrf=False)
    def challenge(self, **kwargs):
        """Issue a one-time challenge; it does not grant driver API access."""
        if request_payload_too_large(2048):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        data = read_json_body()
        approval_id = data.get('approval_id')
        credential = str(data.get('activation_credential') or '')
        if not isinstance(approval_id, int) or not 32 <= len(credential) <= 128:
            return error('INVALID_DEVICE_CREDENTIAL', 'اعتماد الجهاز غير صالح.', status=401)
        model = request.env['trnsp.driver.device.approval'].sudo()
        rec = model.browse(approval_id).exists()
        if not rec:
            return error('INVALID_DEVICE_CREDENTIAL', 'اعتماد الجهاز غير صالح.', status=401)
        request.env.cr.execute('SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE', (rec.id,))
        rec.invalidate_cache()
        digest = hashlib.sha256(credential.encode('utf-8')).hexdigest()
        if rec.state != 'approved' or not rec.activation_used_at or not rec.credential_hash or not hmac.compare_digest(rec.credential_hash, digest) or rec.database_name != request.db:
            return error('INVALID_DEVICE_CREDENTIAL', 'اعتماد الجهاز غير صالح.', status=401)
        nonce = secrets.token_urlsafe(32)
        rec.write({
            'proof_challenge_hash': hashlib.sha256(nonce.encode('ascii')).hexdigest(),
            'proof_challenge_expires_at': fields.Datetime.now() + timedelta(minutes=2),
            'proof_challenge_used_at': False,
        })
        return ok({'challenge': nonce, 'expires_in_seconds': 120})

    @http.route('/api/driver/v1/device-approval/verify', type='json', auth='public', methods=['POST'], csrf=False)
    def verify(self, **kwargs):
        """Verify proof of possession of the approved Ed25519 private key.

        Signed UTF-8 message: QIMAM-DEVICE-PROOF\n<database>\n<approval_id>\n<challenge>
        This endpoint intentionally does not issue a driver bearer token.
        """
        if request_payload_too_large(4096):
            return error('PAYLOAD_TOO_LARGE', 'الطلب كبير جدًا.', status=413)
        if Ed25519PublicKey is None:
            return error('CRYPTO_UNAVAILABLE', 'خدمة التوقيع غير متاحة.', status=503)
        data = read_json_body()
        approval_id = data.get('approval_id')
        credential = str(data.get('activation_credential') or '')
        nonce = str(data.get('challenge') or '')
        signature = str(data.get('signature') or '')
        if not isinstance(approval_id, int) or not 32 <= len(credential) <= 128 or not 32 <= len(nonce) <= 128 or len(signature) > 256:
            return error('INVALID_PROOF', 'إثبات الجهاز غير صالح.', status=401)
        rec = request.env['trnsp.driver.device.approval'].sudo().browse(approval_id).exists()
        if not rec:
            return error('INVALID_PROOF', 'إثبات الجهاز غير صالح.', status=401)
        request.env.cr.execute('SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE', (rec.id,))
        rec.invalidate_cache()
        now = fields.Datetime.now()
        digest = hashlib.sha256(credential.encode('utf-8')).hexdigest()
        challenge_digest = hashlib.sha256(nonce.encode('ascii', errors='ignore')).hexdigest()
        valid = (rec.state == 'approved' and rec.activation_used_at and rec.database_name == request.db
                 and rec.credential_hash and hmac.compare_digest(rec.credential_hash, digest)
                 and rec.proof_challenge_hash and hmac.compare_digest(rec.proof_challenge_hash, challenge_digest)
                 and not rec.proof_challenge_used_at and rec.proof_challenge_expires_at
                 and fields.Datetime.to_datetime(rec.proof_challenge_expires_at) >= fields.Datetime.to_datetime(now))
        if not valid:
            return error('INVALID_PROOF', 'إثبات الجهاز غير صالح.', status=401)
        # Consume challenge even when signature is invalid, preventing brute-force retries.
        rec.write({'proof_challenge_hash': False, 'proof_challenge_used_at': now})
        try:
            key = base64.urlsafe_b64decode(rec.public_key + '=' * (-len(rec.public_key) % 4))
            sig = base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4))
            message = ('QIMAM-DEVICE-PROOF\n%s\n%s\n%s' % (request.db, rec.id, nonce)).encode('utf-8')
            Ed25519PublicKey.from_public_bytes(key).verify(sig, message)
        except (ValueError, binascii.Error, InvalidSignature):
            return error('INVALID_PROOF', 'إثبات الجهاز غير صالح.', status=401)
        return ok({'verified': True, 'approval_id': rec.id})
