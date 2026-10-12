# -*- coding: utf-8 -*-
from odoo import fields, models


class DriverDeviceProofNonce(models.Model):
    _name = 'trnsp.driver.device.proof.nonce'
    _description = 'منع إعادة استخدام توقيع جهاز السائق'
    _order = 'id desc'

    approval_id = fields.Many2one('trnsp.driver.device.approval', required=True, ondelete='cascade', index=True)
    nonce = fields.Char(required=True, index=True)

    _sql_constraints = [
        ('unique_device_proof_nonce', 'unique(approval_id, nonce)', 'Device proof nonce already used.'),
    ]
