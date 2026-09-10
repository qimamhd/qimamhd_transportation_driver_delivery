# -*- coding: utf-8 -*-

import re

from passlib.context import CryptContext

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


_APP_PASSWORD_CONTEXT = CryptContext(
    schemes=['pbkdf2_sha512'],
    deprecated='auto'
)


class HrEmployeeDriverApp(models.Model):
    _inherit = 'hr.employee'

    branch_id = fields.Many2one(
        'custom.branches',
        string='الفرع',
        default=lambda self: self.env.user.branch_id
        if 'branch_id' in self.env.user._fields else False,
        help='الفرع التشغيلي للسائق. يستخدمه تطبيق السائق عند إنشاء ملف التوصيلات الشهري.'
    )

    app_access_enabled = fields.Boolean(
        string='السماح بالدخول لتطبيق السائق',
        default=False,
        copy=False
    )

    # Legacy field kept for database compatibility only.
    # Driver-app authentication now uses hr.employee.identification_id.
    app_login = fields.Char(
        string='اسم الدخول القديم',
        copy=False,
        index=True,
        help='حقل قديم غير مستخدم في تسجيل دخول تطبيق السائق.'
    )

    # Non-stored input fields: plaintext is never persisted in PostgreSQL.
    new_app_pin = fields.Char(
        string='PIN جديد',
        copy=False,
        store=False,
        help='أدخل PIN من 4 إلى 6 أرقام. لا يتم تخزين القيمة نفسها؛ يتم حفظ Hash فقط.'
    )

    new_app_password = fields.Char(
        string='كلمة مرور جديدة',
        copy=False,
        store=False,
        help='لا يتم تخزين كلمة المرور نفسها؛ يتم حفظ Hash فقط.'
    )

    app_pin_hash = fields.Char(
        string='PIN Hash',
        copy=False,
        readonly=True,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    app_password_hash = fields.Char(
        string='Password Hash',
        copy=False,
        readonly=True,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    biometric_allowed = fields.Boolean(
        string='السماح بفتح التطبيق بالبصمة/Face ID',
        default=True,
        copy=False,
        help='البصمة نفسها لا تُحفظ في Odoo. التطبيق يستخدم حماية الجهاز لفتح جلسة محفوظة بأمان.'
    )

    app_credentials_updated_at = fields.Datetime(
        string='آخر تحديث لبيانات الدخول',
        readonly=True,
        copy=False
    )

    app_last_login = fields.Datetime(
        string='آخر دخول للتطبيق',
        readonly=True,
        copy=False
    )

    app_device_id = fields.Char(
        string='معرف الجهاز المعتمد',
        readonly=True,
        copy=False,
        index=True,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    app_device_name = fields.Char(
        string='الجهاز المعتمد',
        readonly=True,
        copy=False,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    app_device_bound_at = fields.Datetime(
        string='تاريخ اعتماد الجهاز',
        readonly=True,
        copy=False,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    app_device_last_login_at = fields.Datetime(
        string='آخر دخول من الجهاز المعتمد',
        readonly=True,
        copy=False,
        groups='qimamhd_transportation_driver_delivery.group_driver_request_manager'
    )

    app_failed_attempts = fields.Integer(
        string='محاولات الدخول الفاشلة',
        default=0,
        readonly=True,
        copy=False
    )

    app_locked_until = fields.Datetime(
        string='حظر الدخول حتى',
        readonly=True,
        copy=False
    )

    _sql_constraints = [
        (
            'driver_app_login_uniq',
            'unique(app_login)',
            'اسم الدخول/رقم الجوال مستخدم لسائق آخر.'
        ),
    ]

    def _check_driver_app_manager(self):
        if not self.env.user.has_group(
            'qimamhd_transportation_driver_delivery.group_driver_request_manager'
        ):
            raise AccessError(
                _('ليس لديك صلاحية إدارة بيانات دخول تطبيق السائقين.')
            )

    @api.model
    def _validate_pin_value(self, pin):
        if pin in (False, None, ''):
            return
        if not re.match(r'^\d{4,6}$', str(pin)):
            raise ValidationError(
                _('PIN يجب أن يتكون من 4 إلى 6 أرقام فقط.')
            )

    @api.model
    def _prepare_app_credentials_vals(self, vals):
        vals = dict(vals)

        pin = vals.pop('new_app_pin', None)
        password = vals.pop('new_app_password', None)

        if pin not in (None, False, ''):
            self._validate_pin_value(pin)
            vals['app_pin_hash'] = _APP_PASSWORD_CONTEXT.hash(str(pin))
            vals['app_credentials_updated_at'] = fields.Datetime.now()

        if password not in (None, False, ''):
            if len(str(password)) < 6:
                raise ValidationError(
                    _('كلمة مرور التطبيق يجب ألا تقل عن 6 أحرف.')
                )
            vals['app_password_hash'] = _APP_PASSWORD_CONTEXT.hash(str(password))
            vals['app_credentials_updated_at'] = fields.Datetime.now()

        return vals

    @api.model
    def create(self, vals):
        protected_keys = {
            'branch_id',
            'app_access_enabled',
            'new_app_pin',
            'new_app_password',
            'biometric_allowed',
            'app_pin_hash',
            'app_password_hash',
        }
        if protected_keys.intersection(vals.keys()):
            self._check_driver_app_manager()

        vals = self._prepare_app_credentials_vals(vals)
        rec = super(HrEmployeeDriverApp, self).create(vals)
        rec._validate_app_access_configuration()
        return rec

    def write(self, vals):
        managed_credentials_changed = any(
            key in vals for key in (
                'branch_id',
                'new_app_pin',
                'new_app_password',
                'app_access_enabled',
                'biometric_allowed',
            )
        )
        # identification_id is an HR employee field, so normal HR permissions
        # continue to control it. If it changes, existing app sessions are
        # revoked because it is now the driver's login identity.
        login_identity_changed = 'identification_id' in vals

        if managed_credentials_changed:
            self._check_driver_app_manager()

        vals = self._prepare_app_credentials_vals(vals)
        result = super(HrEmployeeDriverApp, self).write(vals)

        # Validate the driver-app configuration only when configuration or
        # login identity fields are actually changed. Runtime login metadata
        # (failed attempts, lock time, last login) must never turn an invalid
        # credential attempt into an Odoo ValidationError/500 response.
        if managed_credentials_changed or login_identity_changed:
            self._validate_app_access_configuration()

        if managed_credentials_changed or login_identity_changed:
            sessions = self.env['trnsp.driver.app.session'].sudo().search([
                ('employee_id', 'in', self.ids),
                ('revoked', '=', False),
            ])
            if sessions:
                sessions.write({'revoked': True})

            # Password/identity/access/biometric policy changes must also revoke
            # persistent device credentials so biometric login can never bypass
            # an administrator's security change.
            biometric_credentials = self.env[
                'trnsp.driver.biometric.credential'
            ].sudo().search([
                ('employee_id', 'in', self.ids),
                ('revoked', '=', False),
            ])
            if biometric_credentials:
                biometric_credentials.write({'revoked': True})

        return result

    def _validate_app_access_configuration(self):
        for rec in self:
            if not rec.app_access_enabled:
                continue

            if not rec.driver_emp:
                raise ValidationError(
                    _('لا يمكن تفعيل دخول التطبيق إلا لموظف معرف كسائق.')
                )

            if not rec.branch_id:
                raise ValidationError(
                    _('يجب تحديد الفرع قبل تفعيل دخول الموظف إلى تطبيق السائق.')
                )

            if not rec.identification_id:
                raise ValidationError(
                    _('يجب تحديد رقم الهوية للموظف قبل تفعيل دخول تطبيق السائق.')
                )

            duplicate = self.sudo().search([
                ('id', '!=', rec.id),
                ('driver_emp', '=', True),
                ('app_access_enabled', '=', True),
                ('identification_id', '=', rec.identification_id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _('رقم الهوية مستخدم مسبقًا لحساب سائق آخر مفعّل في التطبيق.')
                )

            if not rec.app_password_hash:
                raise ValidationError(
                    _('يجب تعيين كلمة مرور للتطبيق قبل تفعيل دخول السائق.')
                )

    def _single_device_policy_enabled(self):
        self.ensure_one()
        return bool(self.company_id and self.company_id.driver_app_single_device)

    def check_or_bind_app_device(self, device_id, device_name=False):
        """Atomically validate/bind this driver's approved device.

        Called only after password verification. The row lock prevents two
        simultaneous first-login requests from binding two different devices.
        Returns (allowed, newly_bound).
        """
        self.ensure_one()
        if not self._single_device_policy_enabled():
            return True, False

        device_id = str(device_id or '').strip()
        if not device_id or len(device_id) > 128:
            return False, False

        self.env.cr.execute(
            'SELECT id FROM hr_employee WHERE id = %s FOR UPDATE',
            (self.id,),
        )
        self.invalidate_cache([
            'app_device_id', 'app_device_name', 'app_device_bound_at',
            'app_device_last_login_at',
        ])
        current = (self.app_device_id or '').strip()
        now = fields.Datetime.now()
        if current and current != device_id:
            return False, False

        vals = {'app_device_last_login_at': now}
        newly_bound = not bool(current)
        if newly_bound:
            vals.update({
                'app_device_id': device_id,
                'app_device_name': (str(device_name or '').strip()[:128] or 'Qimam Route Mobile'),
                'app_device_bound_at': now,
            })
        elif device_name and self.app_device_name != str(device_name).strip()[:128]:
            vals['app_device_name'] = str(device_name).strip()[:128]
        super(HrEmployeeDriverApp, self).write(vals)
        return True, newly_bound

    def action_unbind_app_device(self):
        """Manager-only device reset; revoke all active app access tokens."""
        self._check_driver_app_manager()
        sessions = self.env['trnsp.driver.app.session'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('revoked', '=', False),
        ])
        if sessions:
            sessions.write({'revoked': True})
        credentials = self.env['trnsp.driver.biometric.credential'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('revoked', '=', False),
        ])
        if credentials:
            credentials.write({'revoked': True})
        super(HrEmployeeDriverApp, self).write({
            'app_device_id': False,
            'app_device_name': False,
            'app_device_bound_at': False,
            'app_device_last_login_at': False,
        })
        return True

    def verify_app_pin(self, pin):
        self.ensure_one()
        if not self.app_access_enabled or not self.app_pin_hash:
            return False
        try:
            return _APP_PASSWORD_CONTEXT.verify(
                str(pin or ''),
                self.app_pin_hash
            )
        except Exception:
            return False

    def verify_app_password(self, password):
        self.ensure_one()
        if not self.app_access_enabled or not self.app_password_hash:
            return False
        try:
            return _APP_PASSWORD_CONTEXT.verify(
                str(password or ''),
                self.app_password_hash
            )
        except Exception:
            return False

    def action_unlock_app_login(self):
        """Manager-only manual unlock without changing credentials or sessions."""
        self._check_driver_app_manager()
        self.write({
            'app_failed_attempts': 0,
            'app_locked_until': False,
        })
        return True

    def action_clear_app_credentials(self):
        self._check_driver_app_manager()
        self.write({
            'app_access_enabled': False,
            'app_pin_hash': False,
            'app_password_hash': False,
            'app_failed_attempts': 0,
            'app_locked_until': False,
            'app_credentials_updated_at': fields.Datetime.now(),
        })
        return True
