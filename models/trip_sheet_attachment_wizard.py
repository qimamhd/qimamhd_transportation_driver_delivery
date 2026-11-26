# -*- coding: utf-8 -*-

import base64
import binascii

from odoo import fields, models, _
from odoo.exceptions import ValidationError

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


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

        try:
            raw = base64.b64decode(self.attachment or b'', validate=False)
        except (TypeError, ValueError, binascii.Error):
            raw = b''
        if len(raw) > MAX_ATTACHMENT_BYTES:
            raise ValidationError(_('حجم المرفق أكبر من 5 ميجابايت.'))
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):
            ext = 'png'
        elif raw.startswith(b'\xff\xd8\xff'):
            ext = 'jpg'
        else:
            raise ValidationError(_('المرفق يجب أن يكون صورة بصيغة JPG أو PNG.'))

        line.write({
            'trip_sheet_image': self.attachment,
            'trip_sheet_image_name': self.attachment_name or ('trip_sheet.%s' % ext),
        })
        return {'type': 'ir.actions.act_window_close'}
