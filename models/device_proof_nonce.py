# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DriverDeviceProofNonce(models.Model):
    _name = 'trnsp.driver.device.proof.nonce'
    _description = 'منع إعادة استخدام توقيع جهاز السائق'
    _order = 'id desc'

    approval_id = fields.Many2one('trnsp.driver.device.approval', required=True, ondelete='cascade', index=True)
    nonce = fields.Char(required=True, index=True)

    _sql_constraints = [
        ('unique_device_proof_nonce', 'unique(approval_id, nonce)', 'Device proof nonce already used.'),
    ]

    @api.model
    def _cron_cleanup_driver_app_records(self):
        """Delete records that no longer protect anything.

        - Proof nonces older than 1 day: the server rejects any proof whose
          timestamp is more than 90 seconds off, so an old nonce can never be
          replayed anyway.
        - App sessions and biometric credentials that expired or were revoked
          more than 30 days ago (kept 30 days for review).
        """
        now = fields.Datetime.now()
        nonce_cutoff = now - timedelta(days=1)
        keep_cutoff = now - timedelta(days=30)
        nonces = self.sudo().search([('create_date', '<', nonce_cutoff)])
        nonce_count = len(nonces)
        nonces.unlink()
        counts = {'nonces': nonce_count}
        for key, model in (('sessions', 'trnsp.driver.app.session'),
                           ('biometric', 'trnsp.driver.biometric.credential')):
            records = self.env[model].sudo().search([
                '|',
                ('expires_at', '<', keep_cutoff),
                '&', ('revoked', '=', True), ('write_date', '<', keep_cutoff),
            ])
            counts[key] = len(records)
            records.unlink()
        _logger.info('QIMAM_CLEANUP: deleted %s', counts)
        return counts
