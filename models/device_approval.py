# -*- coding: utf-8 -*-
"""Administrative approval records; enforcement is intentionally not enabled yet."""
import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class DriverDeviceApproval(models.Model):
    _name = 'trnsp.driver.device.approval'
    _description = 'طلب اعتماد اتصال تطبيق السائق'
    _order = 'id desc'

    name = fields.Char(default=lambda self: _('طلب اعتماد جديد'), readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    device_id = fields.Char(required=True, readonly=True, index=True)
    device_name = fields.Char(readonly=True)
    database_name = fields.Char(required=True, readonly=True)
    server_origin = fields.Char(required=True, readonly=True)
    public_key = fields.Text(required=True, readonly=True, help='Public signing key supplied by device; never store private keys here.')
    request_nonce = fields.Char(required=True, readonly=True, index=True)
    state = fields.Selection([
        ('pending', 'بانتظار الموافقة'), ('approved', 'موافق عليه'),
        ('rejected', 'مرفوض'), ('revoked', 'ملغى'),
    ], default='pending', required=True, readonly=True, index=True)
    reviewed_by = fields.Many2one('res.users', readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    activation_hash = fields.Char(readonly=True, copy=False, groups='base.group_system')
    activation_expires_at = fields.Datetime(readonly=True)
    activation_used_at = fields.Datetime(readonly=True)
    failed_attempts = fields.Integer(default=0, readonly=True)
    credential_hash = fields.Char(readonly=True, copy=False, groups='base.group_system')
    proof_challenge_hash = fields.Char(readonly=True, copy=False, groups='base.group_system')
    proof_challenge_expires_at = fields.Datetime(readonly=True)
    proof_challenge_used_at = fields.Datetime(readonly=True)


    _sql_constraints = [
        ('approval_nonce_unique', 'unique(request_nonce)', 'Duplicate approval request.'),
    ]

    def _require_manager(self):
        if not self.env.user.has_group('qimamhd_transportation_driver_delivery.group_driver_request_manager'):
            raise AccessError(_('Only driver app managers may review device approvals.'))

    def action_approve(self):
        self.ensure_one()
        self._require_manager()
        if self.state != 'pending':
            raise UserError(_('Only pending requests can be approved.'))
        code = secrets.token_urlsafe(24)
        self.write({
            'state': 'approved',
            'reviewed_by': self.env.uid,
            'reviewed_at': fields.Datetime.now(),
            'activation_hash': hashlib.sha256(code.encode('utf-8')).hexdigest(),
            'activation_expires_at': fields.Datetime.now() + timedelta(minutes=5),
            'failed_attempts': 0,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('رمز التفعيل - يظهر مرة واحدة'),
            'res_model': 'trnsp.driver.activation.display',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.env['trnsp.driver.activation.display'].create({'code': code}).id,
        }

    def action_reject(self):
        self._require_manager()
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be rejected.'))
        self.write({'state': 'rejected', 'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})

    def action_revoke(self):
        self._require_manager()
        self.write({'state': 'revoked', 'activation_hash': False, 'credential_hash': False, 'proof_challenge_hash': False})


class DriverActivationDisplay(models.TransientModel):
    _name = 'trnsp.driver.activation.display'
    _description = 'عرض رمز تفعيل الجهاز مرة واحدة'

    code = fields.Char(readonly=True)
