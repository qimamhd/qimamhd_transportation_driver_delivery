# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

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

    @http.route(
        '/api/driver/v1/branding',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def branding(self, **kwargs):
        # Presentation-only endpoint used before login. It deliberately exposes
        # only the configured company display name/logo; no database, version,
        # users, branches, IDs, or deployment details are returned.
        company = request.env['res.company'].sudo().search([], order='id', limit=1)
        logo_base64 = False
        if company:
            logo_value = False
            if 'logo' in company._fields:
                logo_value = company.logo
            elif company.partner_id and 'image_1920' in company.partner_id._fields:
                logo_value = company.partner_id.image_1920
            if logo_value:
                if isinstance(logo_value, bytes):
                    try:
                        logo_base64 = logo_value.decode('ascii')
                    except UnicodeDecodeError:
                        logo_base64 = False
                else:
                    logo_base64 = str(logo_value)

        return ok({
            'company_name': company.name if company else False,
            'logo_base64': logo_base64,
        })

