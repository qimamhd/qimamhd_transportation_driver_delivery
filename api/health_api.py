# -*- coding: utf-8 -*-

from odoo import http

from .common import ok


class DriverAppHealthAPI(http.Controller):

    @http.route(
        '/api/driver/v1/ping',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def ping(self, **kwargs):
        # Intentionally returns no database, company, Odoo version, paths, or
        # other deployment details. Used by Qimam Route connection setup only.
        return ok({
            'service': 'Qimam Route Driver API',
            'api_version': 'v1',
            'ready': True,
        })
