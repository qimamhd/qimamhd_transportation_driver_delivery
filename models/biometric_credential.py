# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class DriverBiometricCredential(models.Model):
    _name = 'trnsp.driver.biometric.credential'
    _description = 'اعتماد الدخول بالبصمة لتطبيق السائق'
    _order = 'id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='السائق',
        required=True,
        ondelete='cascade',
        index=True,
    )
    credential_hash = fields.Char(
        string='Credential Hash',
        required=True,
        copy=False,
        index=True,
        readonly=True,
    )
    device_id = fields.Char(
        string='معرف الجهاز',
        required=True,
        copy=False,
        index=True,
        readonly=True,
    )
    device_name = fields.Char(string='الجهاز', readonly=True)
    created_at = fields.Datetime(
        string='تاريخ الإنشاء',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    last_used_at = fields.Datetime(string='آخر استخدام', readonly=True)
    expires_at = fields.Datetime(string='انتهاء الاعتماد', required=True, readonly=True)
    revoked = fields.Boolean(string='ملغى', default=False, readonly=True, index=True)

    _sql_constraints = [
        (
            'driver_biometric_credential_hash_uniq',
            'unique(credential_hash)',
            'Biometric credential duplicated.',
        ),
    ]

    @api.model
    def _hash(self, token):
        return hashlib.sha256((token or '').encode('utf-8')).hexdigest()

    @api.model
    def create_credential(self, employee, device_id, device_name=False, days=None):
        """Create one active credential per driver/device and return its secret once."""
        if days is None:
            raw_days = self.env['ir.config_parameter'].sudo().get_param(
                'qimamhd_transportation_driver_delivery.biometric_credential_days',
                default='180',
            )
            try:
                days = int(raw_days)
            except (TypeError, ValueError):
                days = 180
        days = max(1, min(int(days), 365))

        # Re-enrolling a device invalidates the previous secret for that same
        # driver/device pair, without touching other registered devices.
        old = self.search([
            ('employee_id', '=', employee.id),
            ('device_id', '=', device_id),
            ('revoked', '=', False),
        ])
        if old:
            old.write({'revoked': True})

        token = secrets.token_urlsafe(40)
        now = fields.Datetime.now()
        credential = self.create({
            'employee_id': employee.id,
            'credential_hash': self._hash(token),
            'device_id': device_id,
            'device_name': device_name or False,
            'created_at': now,
            'last_used_at': now,
            'expires_at': now + timedelta(days=days),
        })
        return token, credential

    @api.model
    def find_active(self, token):
        credential = self.search([
            ('credential_hash', '=', self._hash(token)),
            ('revoked', '=', False),
        ], limit=1)
        if credential and credential.is_expired():
            credential.write({'revoked': True})
            return self.browse()
        return credential

    def is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at <= fields.Datetime.now())
