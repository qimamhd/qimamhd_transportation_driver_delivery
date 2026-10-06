# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class DriverDeliveryTripSheetAttachmentWizard(models.TransientModel):
    _name = 'trnsp.driver.delivery.trip.sheet.attachment.wizard'
    _description = 'إضافة مرفق شيت الرحلة'

    line_id = fields.Many2one(
        'trnsp.store.driver.request.line',
        string='التوصيلة',
        required=True,
        readonly=True,
    )
    attachment = fields.Binary(
        string='المرفق',
        required=True,
        attachment=False,
    )
    attachment_name = fields.Char(string='اسم المرفق')

    def action_confirm(self):
        self.ensure_one()
        line = self.line_id.exists()
        if not line:
            raise ValidationError(_('التوصيلة لم تعد موجودة.'))
        if line.trip_sheet_image:
            raise ValidationError(_('يوجد مرفق لهذه التوصيلة بالفعل. احذف المرفق الحالي أولاً.'))

        line.write({
            'trip_sheet_image': self.attachment,
            'trip_sheet_image_name': self.attachment_name or _('مرفق شيت الرحلة'),
        })
        return {'type': 'ir.actions.act_window_close'}
