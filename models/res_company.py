# -*- coding: utf-8 -*-

from datetime import datetime

import pytz

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    driver_app_timezone = fields.Selection(
        selection=lambda self: [(tz, tz) for tz in pytz.common_timezones],
        string='المنطقة الزمنية المعتمدة للتطبيق',
        required=True,
        default=lambda self: self.env.user.tz or 'UTC',
        help='تُستخدم لحساب الشهر والتاريخ والوقت الموثوق من السيرفر، ولا يعتمد النظام على ساعة هاتف السائق.'
    )

    driver_app_gps_policy = fields.Selection([
        ('strict', 'داخل النطاق فقط'),
        ('review', 'السماح خارج النطاق وإرساله للمراجعة'),
    ], string='سياسة GPS للتوصيلة', required=True, default='strict')

    driver_app_period_policy = fields.Selection([
        ('current_month', 'الشهر الحالي فقط'),
        ('backend_periods', 'فترات التوصيل من الباك إند'),
    ], string='مصدر فترات التطبيق', required=True, default='current_month')

    driver_app_allow_offline = fields.Boolean(
        string='السماح بالتسجيل بدون إنترنت',
        default=False,
        help='عند التعطيل يجب إرسال التوصيلة مباشرة إلى السيرفر، ولا يحفظ التطبيق طلبًا جديدًا في قائمة الانتظار المحلية.'
    )

    driver_app_datetime_policy = fields.Selection([
        ('server_now', 'تاريخ ووقت السيرفر الحالي'),
        ('driver_select', 'السماح للسائق باختيار التاريخ والوقت'),
    ], string='تاريخ ووقت التوصيلة', required=True, default='server_now')

    driver_app_auto_close_previous_months = fields.Boolean(
        string='إغلاق الأشهر السابقة تلقائيًا',
        default=True,
        help='يغلق ملفات السائقين وفترات التوصيل المفتوحة عند انتقال الشهر. ما تعيد الإدارة فتحه يدويًا يبقى مفتوحًا.'
    )

    def _driver_app_timezone(self):
        self.ensure_one()
        return self.driver_app_timezone or self.partner_id.tz or self.env.user.tz or 'UTC'

    def _driver_app_local_now(self):
        """Trusted current datetime derived from server UTC, localized by company timezone."""
        self.ensure_one()
        raw = fields.Datetime.from_string(fields.Datetime.now())
        if raw.tzinfo is None:
            raw = pytz.UTC.localize(raw)
        try:
            zone = pytz.timezone(self._driver_app_timezone())
        except Exception:
            zone = pytz.UTC
        return raw.astimezone(zone)

    def _driver_app_policy_payload(self):
        self.ensure_one()
        now = self._driver_app_local_now()
        return {
            'gps_mode': self.driver_app_gps_policy or 'strict',
            'period_mode': self.driver_app_period_policy or 'current_month',
            'allow_offline': bool(self.driver_app_allow_offline),
            'datetime_mode': self.driver_app_datetime_policy or 'server_now',
            'auto_close_previous_periods': bool(self.driver_app_auto_close_previous_months),
            'server_datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'server_date': now.strftime('%Y-%m-%d'),
            'server_time': now.strftime('%H:%M:%S'),
            'server_year': now.year,
            'server_month': now.month,
            'timezone': self._driver_app_timezone(),
        }

    def _driver_app_auto_close_previous(self):
        """Close stale open periods/batches without touching manager-reopened records."""
        Period = self.env['trnsp.driver.delivery.period'].sudo()
        Batch = self.env['trnsp.store.driver.request.batch'].sudo()
        for company in self.sudo():
            if not company.driver_app_auto_close_previous_months:
                continue
            now = company._driver_app_local_now()
            current_key = (now.year, now.month)

            periods = Period.search([
                ('company_id', '=', company.id),
                ('state', '=', 'open'),
                ('manual_reopened', '=', False),
            ])
            stale_periods = periods.filtered(
                lambda p: (p.year, int(p.month_name)) < current_key
            )
            if stale_periods:
                stale_periods.with_context(period_control_write=True).write({
                    'state': 'closed',
                    'closed_by': self.env.user.id,
                    'closed_at': fields.Datetime.now(),
                })

            batches = Batch.search([
                ('company_id', '=', company.id),
                ('state', '=', 'draft'),
                ('app_manual_reopened', '=', False),
            ])
            stale_batches = batches.filtered(
                lambda b: (b.year, int(b.month_name)) < current_key
            )
            if stale_batches:
                stale_batches.write({'state': 'done'})
        return True

    @api.model
    def _cron_driver_app_auto_close_previous(self):
        companies = self.sudo().search([
            ('driver_app_auto_close_previous_months', '=', True),
        ])
        companies._driver_app_auto_close_previous()
        return True
