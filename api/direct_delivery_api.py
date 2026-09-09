# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from .common import authenticate_driver, error, float_value, ok, read_json_body
from .direct_delivery_logic import (
    get_direct_delivery_context,
    get_max_gps_accuracy,
    match_direct_destination,
    serialize_direct_car,
)


class DriverAppDirectDeliveryAPI(http.Controller):

    @http.route(
        '/api/driver/v1/direct-delivery/setup',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def direct_delivery_setup(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth

        context, failure = get_direct_delivery_context(request.env, driver)
        if failure:
            return error(
                failure['code'], failure['message'],
                status=failure['status'], details=failure.get('details')
            )

        assigned_car = context['assigned_car']
        area = context['area']
        cars = context['cars']
        return ok({
            'assigned_car': serialize_direct_car(assigned_car, assigned_car),
            'cars': [serialize_direct_car(car, assigned_car) for car in cars],
            'source': {
                'id': area.id,
                'name': area.display_name or '',
                'locked': True,
            },
            'destination_mode': 'gps_auto_match',
            'destination_locked': True,
            'allowed_radius': 0.0,
            'max_gps_accuracy': get_max_gps_accuracy(driver),
        })

    @http.route(
        '/api/driver/v1/direct-delivery/match-destination',
        type='json', auth='public', methods=['POST'], csrf=False
    )
    def direct_delivery_match_destination(self, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, session = auth
        data = read_json_body()

        try:
            latitude = float_value(data.get('latitude'), 'latitude')
            longitude = float_value(data.get('longitude'), 'longitude')
            gps_accuracy = (
                float_value(data.get('gps_accuracy'), 'gps_accuracy')
                if data.get('gps_accuracy') not in (None, '') else 0.0
            )
        except (ValueError, TypeError) as exc:
            return error('INVALID_INPUT', str(exc))

        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return error('INVALID_GPS', 'إحداثيات السائق خارج النطاق الصحيح.')
        if gps_accuracy < 0 or gps_accuracy > 10000:
            return error('INVALID_GPS_ACCURACY', 'دقة GPS المرسلة غير صالحة.')

        match, failure = match_direct_destination(
            request.env, driver, latitude, longitude, gps_accuracy=gps_accuracy
        )
        if failure:
            return error(
                failure['code'], failure['message'],
                status=failure['status'], details=failure.get('details')
            )

        destination = match['destination']
        context = match['context']
        return ok({
            'source': {
                'id': context['area'].id,
                'name': context['area'].display_name or '',
            },
            'destination': {
                'id': destination.id,
                'name': destination.display_name or '',
                'gps_configured': True,
                'destination_latitude': match['latitude'],
                'destination_longitude': match['longitude'],
                'allowed_radius': match['allowed_radius'],
            },
            'gps_distance': match['distance'],
            'gps_accuracy': match['gps_accuracy'],
            'effective_distance': match['effective_distance'],
            'allowed_radius': match['allowed_radius'],
            'max_gps_accuracy': get_max_gps_accuracy(driver),
        })
