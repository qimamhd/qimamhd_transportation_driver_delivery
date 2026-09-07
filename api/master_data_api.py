# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from .common import authenticate_driver, company_domain, error, int_value, ok


class DriverAppMasterDataAPI(http.Controller):

    @http.route(
        '/api/driver/v1/sources',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def sources(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth

        Pricing = request.env['trnsp.store.pricing'].sudo()
        domain = [('source_path_id', '!=', False)]
        domain += company_domain(Pricing, driver.company_id)
        headers = Pricing.search(domain)
        sources = headers.mapped('source_path_id')

        return ok([
            {'id': source.id, 'name': source.display_name}
            for source in sources.sorted(key=lambda r: r.display_name or '')
        ])

    @http.route(
        '/api/driver/v1/destinations',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def destinations(self, source_id=None, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth

        try:
            source_id = int_value(source_id, 'source_id')
        except ValueError as exc:
            return error('INVALID_SOURCE', str(exc))

        Pricing = request.env['trnsp.store.pricing'].sudo()
        domain = [('source_path_id', '=', source_id)]
        domain += company_domain(Pricing, driver.company_id)
        headers = Pricing.search(domain)
        if not headers:
            return error(
                'SOURCE_NOT_PRICED',
                'المصدر غير موجود في شاشة التسعيرات.',
                status=404,
            )

        lines = headers.mapped('pricing_lines').filtered(
            lambda line: bool(line.destination_path_id)
        )
        # POST /deliveries uses the first matching pricing line. Preserve that
        # same order here so the mobile preview never reads a different record.
        result = {}
        for line in lines:
            destination = line.destination_path_id
            if destination.id in result:
                continue
            gps_configured = bool(
                line.gbs_from and line.gbs_to and line.gps_radius > 0
            )
            result[destination.id] = {
                'id': destination.id,
                'name': destination.display_name,
                'gps_configured': gps_configured,
                'destination_latitude': line.gbs_from if gps_configured else None,
                'destination_longitude': line.gbs_to if gps_configured else None,
                'allowed_radius': line.gps_radius,
            }

        return ok(sorted(result.values(), key=lambda x: x['name'] or ''))

    @http.route(
        '/api/driver/v1/cars',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def cars(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth

        Product = request.env['product.product'].sudo()
        domain = [('car_flag', '=', True)]
        domain += company_domain(Product, driver.company_id)
        cars = Product.search(domain, order='name')

        return ok([
            {'id': car.id, 'name': car.display_name}
            for car in cars
        ])
