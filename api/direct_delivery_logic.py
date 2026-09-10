# -*- coding: utf-8 -*-

import math

from .common import company_domain


DIRECT_DELIVERY_RADIUS_METERS = 50.0


def get_max_gps_accuracy(driver):
    """Company-controlled critical GPS accuracy; 20 m default, never non-positive."""
    company = driver.company_id.sudo()
    value = float(getattr(company, 'driver_app_max_gps_accuracy', 20.0) or 20.0)
    return max(1.0, value)


def _haversine_meters(lat1, lon1, lat2, lon2):
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    )
    return radius * 2.0 * math.atan2(
        math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))
    )


def _failure(code, message, status=409, details=None):
    return {
        'code': code,
        'message': message,
        'status': status,
        'details': details,
    }


def _vehicle_domain(Product, driver, area_id=None):
    domain = [('car_flag', '=', True)]
    if 'trailer_flag' in Product._fields:
        domain.append(('trailer_flag', '=', False))
    if area_id:
        domain.append(('car_area_id', '=', area_id))
    domain += company_domain(Product, driver.company_id)
    return domain


def get_direct_delivery_context(env, driver):
    """Resolve the direct-delivery operating context from Odoo master data.

    The employee's assigned vehicle is authoritative. Its ``car_area_id`` is
    both the fixed direct-delivery source and the filter for alternative cars.
    Nothing here depends on client-supplied source/car data.
    """
    Product = env['product.product'].sudo()

    if 'car_driver_name' not in Product._fields or 'car_area_id' not in Product._fields:
        return None, _failure(
            'DIRECT_DELIVERY_VEHICLE_FIELDS_MISSING',
            'حقول ربط السائق وموقع المركبة غير متاحة في تعريف المركبات.',
            status=500,
        )

    assigned_domain = _vehicle_domain(Product, driver)
    assigned_domain.append(('car_driver_name', '=', driver.id))
    assigned_car = Product.search(assigned_domain, limit=1)
    if not assigned_car:
        return None, _failure(
            'DRIVER_VEHICLE_NOT_ASSIGNED',
            'لا توجد مركبة مرتبطة بهذا السائق في تعريف السيارات.',
            status=409,
        )

    area = assigned_car.car_area_id
    if not area:
        return None, _failure(
            'DRIVER_VEHICLE_AREA_MISSING',
            'مركبة السائق لا تحتوي على موقع مركبة. حدده من تعريف السيارات أولًا.',
            status=409,
        )

    Pricing = env['trnsp.store.pricing'].sudo()
    pricing_domain = [('source_path_id', '=', area.id)]
    pricing_domain += company_domain(Pricing, driver.company_id)
    pricing_headers = Pricing.search(pricing_domain)
    if not pricing_headers:
        return None, _failure(
            'DRIVER_AREA_SOURCE_NOT_PRICED',
            'موقع مركبة السائق غير معرف كمصدر في شاشة التسعيرات.',
            status=409,
            details={'area_id': area.id, 'area_name': area.display_name},
        )

    cars = Product.search(_vehicle_domain(Product, driver, area_id=area.id), order='name')
    return {
        'assigned_car': assigned_car,
        'area': area,
        'cars': cars,
        'pricing_headers': pricing_headers,
    }, None


def serialize_direct_car(car, assigned_car):
    plate = ''
    if 'en_panel_no' in car._fields:
        plate = car.en_panel_no or ''
    if not plate and 'ar_panel_no' in car._fields:
        plate = car.ar_panel_no or ''
    return {
        'id': car.id,
        'name': car.display_name or '',
        'plate': plate or car.display_name or '',
        'driver_id': car.car_driver_name.id if 'car_driver_name' in car._fields and car.car_driver_name else None,
        'area_id': car.car_area_id.id if 'car_area_id' in car._fields and car.car_area_id else None,
        'area_name': car.car_area_id.display_name if 'car_area_id' in car._fields and car.car_area_id else '',
        'is_default': car.id == assigned_car.id,
    }


def match_direct_destination(env, driver, latitude, longitude, gps_accuracy=0.0):
    context, failure = get_direct_delivery_context(env, driver)
    if failure:
        return None, failure

    accuracy = max(0.0, float(gps_accuracy or 0.0))
    max_accuracy = get_max_gps_accuracy(driver)
    if accuracy <= 0.0 or accuracy > max_accuracy:
        return None, _failure(
            'DIRECT_GPS_ACCURACY_TOO_LOW',
            'دقة GPS غير كافية للتوصيل المباشر. يجب أن تكون %.0f متر أو أقل.' % max_accuracy,
            status=409,
            details={
                'gps_accuracy': accuracy,
                'max_gps_accuracy': max_accuracy,
            },
        )
    candidates = []
    seen_destination_ids = set()

    # Preserve pricing line order, but evaluate every unique configured
    # destination and choose the physically nearest valid match.
    for line in context['pricing_headers'].mapped('pricing_lines'):
        destination = line.destination_path_id
        if not destination or destination.id in seen_destination_ids:
            continue
        seen_destination_ids.add(destination.id)

        dest_lat = float(line.gbs_from or 0.0)
        dest_lon = float(line.gbs_to or 0.0)
        configured = (
            -90.0 <= dest_lat <= 90.0
            and -180.0 <= dest_lon <= 180.0
            and (dest_lat != 0.0 or dest_lon != 0.0)
        )
        if not configured:
            continue

        distance = _haversine_meters(latitude, longitude, dest_lat, dest_lon)
        # Keep the same conservative GPS hardening used by the existing app:
        # a point counts as inside only when the uncertainty radius also fits.
        effective_distance = distance + accuracy
        candidates.append({
            'destination': destination,
            'pricing_line': line,
            'latitude': dest_lat,
            'longitude': dest_lon,
            'distance': distance,
            'effective_distance': effective_distance,
        })

    if not candidates:
        return None, _failure(
            'DIRECT_DESTINATIONS_GPS_NOT_CONFIGURED',
            'لا توجد وجهات بإحداثيات GPS صالحة لهذا المصدر.',
            status=409,
            details={
                'source_id': context['area'].id,
                'source_name': context['area'].display_name,
                'allowed_radius': DIRECT_DELIVERY_RADIUS_METERS,
            },
        )

    nearest = min(candidates, key=lambda item: (item['effective_distance'], item['distance']))
    if nearest['effective_distance'] > DIRECT_DELIVERY_RADIUS_METERS:
        return None, _failure(
            'DIRECT_DESTINATION_NOT_MATCHED',
            'موقعك الحالي لا يطابق أي وجهة معتمدة لهذا المصدر ضمن 50 متر.',
            status=409,
            details={
                'source_id': context['area'].id,
                'source_name': context['area'].display_name,
                'nearest_destination_id': nearest['destination'].id,
                'nearest_destination_name': nearest['destination'].display_name,
                'nearest_distance': nearest['distance'],
                'gps_accuracy': accuracy,
                'effective_distance': nearest['effective_distance'],
                'allowed_radius': DIRECT_DELIVERY_RADIUS_METERS,
            },
        )

    nearest['context'] = context
    nearest['gps_accuracy'] = accuracy
    return nearest, None


def validate_direct_delivery_submission(
    env, driver, car_id, source_id, destination_id, latitude, longitude, gps_accuracy=0.0
):
    """Server-authoritative validation for only ``submission_context=direct_delivery``."""
    match, failure = match_direct_destination(
        env, driver, latitude, longitude, gps_accuracy=gps_accuracy
    )
    if failure:
        return None, failure

    context = match['context']
    allowed_car_ids = set(context['cars'].ids)
    if car_id not in allowed_car_ids:
        return None, _failure(
            'DIRECT_CAR_OUTSIDE_DRIVER_AREA',
            'السيارة المحددة ليست من سيارات موقع مركبة السائق.',
            status=409,
            details={
                'car_id': car_id,
                'source_area_id': context['area'].id,
                'source_area_name': context['area'].display_name,
            },
        )

    if source_id != context['area'].id:
        return None, _failure(
            'DIRECT_SOURCE_MISMATCH',
            'مصدر التوصيل المباشر يجب أن يكون موقع مركبة السائق.',
            status=409,
            details={
                'expected_source_id': context['area'].id,
                'expected_source_name': context['area'].display_name,
            },
        )

    if destination_id != match['destination'].id:
        return None, _failure(
            'DIRECT_DESTINATION_MISMATCH',
            'الوجهة المرسلة لا تطابق الوجهة المحددة تلقائيًا من موقع السائق الحالي.',
            status=409,
            details={
                'expected_destination_id': match['destination'].id,
                'expected_destination_name': match['destination'].display_name,
                'gps_distance': match['distance'],
                'gps_accuracy': match['gps_accuracy'],
                'effective_distance': match['effective_distance'],
                'allowed_radius': DIRECT_DELIVERY_RADIUS_METERS,
            },
        )

    return match, None


def validate_route_trip_submission(
    env, driver, car_id, source_id, gps_accuracy=0.0
):
    """Validate shared vehicle/source defaults for the full Start New Trip flow.

    Unlike direct delivery, the destination remains explicitly selected by the
    driver from the source's configured destinations. This validation only
    locks the vehicle area/source and requires the company-configured GPS accuracy checkpoint; the
    existing company GPS/radius policy continues to validate the selected
    destination later in delivery_api.py.
    """
    context, failure = get_direct_delivery_context(env, driver)
    if failure:
        return None, failure

    accuracy = max(0.0, float(gps_accuracy or 0.0))
    max_accuracy = get_max_gps_accuracy(driver)
    if accuracy <= 0.0 or accuracy > max_accuracy:
        return None, _failure(
            'ROUTE_GPS_ACCURACY_TOO_LOW',
            'دقة GPS غير كافية لبدء/إنهاء الرحلة. يجب أن تكون %.0f متر أو أقل.' % max_accuracy,
            status=409,
            details={
                'gps_accuracy': accuracy,
                'max_gps_accuracy': max_accuracy,
            },
        )

    if car_id not in set(context['cars'].ids):
        return None, _failure(
            'ROUTE_CAR_OUTSIDE_DRIVER_AREA',
            'السيارة المحددة ليست من سيارات موقع مركبة السائق.',
            status=409,
            details={
                'car_id': car_id,
                'source_area_id': context['area'].id,
                'source_area_name': context['area'].display_name,
            },
        )

    if source_id != context['area'].id:
        return None, _failure(
            'ROUTE_SOURCE_MISMATCH',
            'مصدر الرحلة يجب أن يكون موقع مركبة السائق.',
            status=409,
            details={
                'expected_source_id': context['area'].id,
                'expected_source_name': context['area'].display_name,
            },
        )

    return context, None
