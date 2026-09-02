# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class DriverDeliveryExceptionAcceptWizard(models.TransientModel):
    _name = 'trnsp.driver.delivery.exception.accept.wizard'
    _description = 'قبول استثنائي لتوصيلة خارج نطاق GPS'

    line_id = fields.Many2one(
        'trnsp.store.driver.request.line',
        string='التوصيلة',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='سبب القبول الاستثنائي',
        required=True,
        help='اكتب سبباً واضحاً يبرر قبول التوصيلة رغم أن موقع السائق خارج النطاق المسموح.'
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'qimamhd_transportation_driver_delivery.group_driver_request_manager'
        ):
            raise AccessError(_('هذه العملية متاحة لمدير طلبات تطبيق السائقين فقط.'))

        line = self.line_id.exists()
        if not line:
            raise ValidationError(_('التوصيلة لم تعد موجودة.'))
        if line.batch_id.state != 'review':
            raise ValidationError(_('القبول الاستثنائي متاح فقط أثناء حالة قيد المراجعة.'))
        if line.gps_valid:
            raise ValidationError(_('هذه التوصيلة داخل نطاق GPS؛ استخدم القبول العادي.'))

        reason = (self.reason or '').strip()
        if not reason:
            raise ValidationError(_('سبب القبول الاستثنائي إلزامي.'))

        line.with_context(
            driver_delivery_workflow_write=True,
            driver_delivery_exception_accept=True,
        ).write({
            'review_state': 'accepted',
            'reject_reason': False,
            'gps_exception_approved': True,
            'gps_exception_reason': reason,
            'gps_exception_user_id': self.env.user.id,
            'gps_exception_date': fields.Datetime.now(),
        })

        line.batch_id.message_post(
            body=_(
                'تم قبول التوصيلة %s استثنائياً خارج نطاق GPS بواسطة %s. السبب: %s'
            ) % (line.display_name, self.env.user.display_name, reason)
        )
        return {'type': 'ir.actions.act_window_close'}
