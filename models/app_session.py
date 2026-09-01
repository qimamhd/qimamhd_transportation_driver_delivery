# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class DriverAppSession(models.Model):
    _name = 'trnsp.driver.app.session'
    _description = 'جلسات تطبيق السائق'
    _order = 'id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='السائق',
        required=True,
        ondelete='cascade',
        index=True,
    )
    token_hash = fields.Char(
        string='Token Hash',
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
    expires_at = fields.Datetime(string='انتهاء الجلسة', required=True, readonly=True)
    revoked = fields.Boolean(string='ملغاة', default=False, readonly=True, index=True)

    _sql_constraints = [
        ('driver_app_token_hash_uniq', 'unique(token_hash)', 'Token session duplicated.'),
    ]

    @api.model
    def create_session(self, employee, device_name=False, days=None):
        # Keep the existing 30-day behavior by default, while allowing a system
        # administrator to shorten it without changing mobile code.
        if days is None:
            raw_days = self.env['ir.config_parameter'].sudo().get_param(
                'qimamhd_transportation_driver_delivery.session_days',
                default='30',
            )
            try:
                days = int(raw_days)
            except (TypeError, ValueError):
                days = 30
        days = max(1, min(int(days), 30))

        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        now = fields.Datetime.now()
        session = self.create({
            'employee_id': employee.id,
            'token_hash': digest,
            'device_name': device_name or False,
            'created_at': now,
            'last_used_at': now,
            'expires_at': now + timedelta(days=days),
        })
        return token, session

    def is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at <= fields.Datetime.now())
