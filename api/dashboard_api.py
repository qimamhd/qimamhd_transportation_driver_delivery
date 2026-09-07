# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import http, fields
from odoo.http import request

from .common import authenticate_driver, error, ok


class DriverAppDashboardAPI(http.Controller):

    @staticmethod
    def _valid_year(value):
        try:
            year = int(value)
        except (TypeError, ValueError):
            return False
        return year if 2000 <= year <= 2100 else False

    @staticmethod
    def _empty_months():
        return {
            month: {
                'month': month,
                'total': 0,
                'accepted': 0,
                'rejected': 0,
                'pending': 0,
            }
            for month in range(1, 13)
        }

    @classmethod
    def _year_stats(cls, driver_id, year):
        Line = request.env['trnsp.store.driver.request.line'].sudo()
        months = cls._empty_months()
        totals = {'total': 0, 'accepted': 0, 'rejected': 0, 'pending': 0}

        groups = Line.read_group(
            [('driver_id', '=', driver_id), ('year', '=', year)],
            ['month_name', 'review_state'],
            ['month_name', 'review_state'],
            lazy=False,
        )
        for group in groups:
            try:
                month = int(group.get('month_name') or 0)
            except (TypeError, ValueError):
                continue
            if month not in months:
                continue
            count = int(group.get('__count') or 0)
            state = group.get('review_state') or 'pending'
            months[month]['total'] += count
            totals['total'] += count
            if state in ('accepted', 'rejected', 'pending'):
                months[month][state] += count
                totals[state] += count

        return {
            'year': year,
            'totals': totals,
            'months': [months[month] for month in range(1, 13)],
        }

    @http.route(
        '/api/driver/v1/dashboard',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def dashboard(self, year=None, **kwargs):
        auth, response = authenticate_driver()
        if response:
            return response
        driver, _session = auth

        current_year = datetime.utcnow().year
        selected_year = self._valid_year(year) or current_year
        if not selected_year:
            return error('INVALID_YEAR', 'السنة غير صحيحة.', status=400)

        Line = request.env['trnsp.store.driver.request.line'].sudo()
        year_groups = Line.read_group(
            [('driver_id', '=', driver.id)],
            ['year'],
            ['year'],
            lazy=False,
        )
        years = set()
        for group in year_groups:
            try:
                value = int(group.get('year') or 0)
            except (TypeError, ValueError):
                continue
            if 2000 <= value <= 2100:
                years.add(value)
        years.add(current_year)
        years.add(selected_year)

        current = self._year_stats(driver.id, selected_year)
        previous = self._year_stats(driver.id, selected_year - 1)

        return ok({
            'selected_year': selected_year,
            'comparison_year': selected_year - 1,
            'available_years': sorted(years, reverse=True),
            'current': current,
            'previous': previous,
            'generated_at': fields.Datetime.now(),
        })
