# -*- coding: utf-8 -*-
"""Administrative approval records; enforcement is intentionally not enabled yet."""
import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

PAIRING_REQUEST_TTL = timedelta(minutes=30)


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
    flow = fields.Selection([
        ('code', 'رمز تفعيل'), ('pairing', 'رمز مطابقة'),
    ], string='طريقة التفعيل', default='code', required=True, readonly=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='السائق', readonly=True, index=True, ondelete='set null')
    match_code = fields.Char(string='رمز المطابقة', readonly=True, copy=False,
                             help='يجب أن يطابق الرمز الظاهر في جوال السائق قبل الموافقة.')


    _sql_constraints = [
        ('approval_nonce_unique', 'unique(request_nonce)', 'Duplicate approval request.'),
    ]

    def _require_manager(self):
        if not self.env.user.has_group('qimamhd_transportation_driver_delivery.group_driver_request_manager'):
            raise AccessError(_('Only driver app managers may review device approvals.'))

    def _issue_activation_code(self):
        """Rotate a short-lived activation code without changing device identity."""
        self.ensure_one()
        code = secrets.token_urlsafe(24)
        # Hash fields are admin-only (groups=base.group_system); callers have
        # already checked the driver-app manager group.
        self.sudo().write({
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

    def action_approve(self):
        self.ensure_one()
        self._require_manager()
        if self.state != 'pending':
            raise UserError(_('Only pending requests can be approved.'))
        if self.flow == 'pairing':
            return self._approve_pairing()
        self.write({
            'state': 'approved',
            'reviewed_by': self.env.uid,
            'reviewed_at': fields.Datetime.now(),
        })
        return self._issue_activation_code()

    def _approve_pairing(self):
        """Approve a match-code request: bind the device to its driver, revoke
        the driver's previous devices. No activation code is shown; the app
        collects its credential with a request signed by the device key."""
        self.env.cr.execute(
            'SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        self.invalidate_cache()
        if self.state != 'pending':
            raise UserError(_('Only pending requests can be approved.'))
        if not self.employee_id:
            raise UserError(_('هذا الطلب غير مربوط بسائق.'))
        if fields.Datetime.to_datetime(self.create_date) < fields.Datetime.now() - PAIRING_REQUEST_TTL:
            raise UserError(_('انتهت صلاحية هذا الطلب. اطلب من السائق إرسال طلب جديد من التطبيق.'))
        now = fields.Datetime.now()
        others = self.sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('id', '!=', self.id),
            ('state', 'in', ('pending', 'approved')),
        ])
        if others:
            others.write({'state': 'revoked', 'activation_hash': False,
                          'credential_hash': False, 'proof_challenge_hash': False})
        self.write({'state': 'approved', 'reviewed_by': self.env.uid, 'reviewed_at': now})
        self.employee_id.sudo()._bind_app_device_from_pairing(self.device_id, self.device_name)
        return True

    def action_reissue_activation(self):
        """Issue a new one-time code for an approved, not-yet-activated device."""
        self.ensure_one()
        self._require_manager()
        # Serialize concurrent reissues and re-read the current record state.
        self.env.cr.execute(
            'SELECT id FROM trnsp_driver_device_approval WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        self.invalidate_cache()
        if self.state != 'approved':
            raise UserError(_('Only approved device requests can receive a new activation code.'))
        if self.activation_used_at:
            raise UserError(_('This device is already activated. Reissuing a code is not allowed.'))
        if self.flow == 'pairing':
            raise UserError(_('طلبات رمز المطابقة لا تحتاج رمز تفعيل.'))
        return self._issue_activation_code()

    def action_reject(self):
        self._require_manager()
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be rejected.'))
        self.write({'state': 'rejected', 'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})

    def action_revoke(self):
        self._require_manager()
        self.sudo().write({'state': 'revoked', 'activation_hash': False, 'credential_hash': False, 'proof_challenge_hash': False})


class DriverActivationDisplay(models.TransientModel):
    _name = 'trnsp.driver.activation.display'
    _description = 'عرض رمز تفعيل الجهاز مرة واحدة'

    code = fields.Char(readonly=True)
