# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


MONTH_SELECTION = [
    ('01', 'يناير'), ('02', 'فبراير'), ('03', 'مارس'), ('04', 'ابريل'),
    ('05', 'مايو'), ('06', 'يونيو'), ('07', 'يوليو'), ('08', 'اغسطس'),
    ('09', 'سبتمبر'), ('10', 'اكتوبر'), ('11', 'نوفمبر'), ('12', 'ديسمبر'),
]


class DriverDeliveryPeriod(models.Model):
    _name = 'trnsp.driver.delivery.period'
    _description = 'إدارة فترات التوصيل'
    _order = 'year desc, month_name desc, id desc'
    _rec_name = 'name'

    month_name = fields.Selection(
        MONTH_SELECTION, string='الشهر', required=True,
        default=lambda self: '%02d' % fields.Date.today().month,
    )
    year = fields.Integer(
        string='السنة', required=True,
        default=lambda self: fields.Date.today().year,
    )
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.user.company_id,
        index=True,
    )
    state = fields.Selection([
        ('open', 'مفتوحة للتسجيل'),
        ('closed', 'مقفلة'),
    ], string='الحالة', required=True, default='open', readonly=True)
    name = fields.Char(string='الفترة', compute='_compute_name', store=True)
    opened_by = fields.Many2one('res.users', string='فتح بواسطة', readonly=True)
    opened_at = fields.Datetime(string='تاريخ الفتح', readonly=True)
    closed_by = fields.Many2one('res.users', string='إغلاق بواسطة', readonly=True)
    closed_at = fields.Datetime(string='تاريخ الإغلاق', readonly=True)
    notes = fields.Text(string='ملاحظات الإدارة')

    _sql_constraints = [
        ('company_period_uniq', 'unique(company_id, month_name, year)',
         'توجد فترة توصيل لنفس الشركة والشهر والسنة مسبقاً.'),
    ]

    @api.depends('month_name', 'year')
    def _compute_name(self):
        labels = dict(MONTH_SELECTION)
        for rec in self:
            month_label = labels.get(rec.month_name, rec.month_name or '')
            rec.name = '%s %s' % (month_label, rec.year or '')

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_('السنة غير صحيحة.'))

    def _check_manager(self):
        if not self.env.user.has_group(
            'qimamhd_transportation_driver_delivery.group_driver_request_manager'
        ):
            raise AccessError(_('ليس لديك صلاحية إدارة فترات التوصيل.'))

    @api.model
    def create(self, vals):
        self._check_manager()
        vals = dict(vals)
        if vals.get('state', 'open') == 'open':
            vals.update({
                'opened_by': self.env.user.id,
                'opened_at': fields.Datetime.now(),
                'closed_by': False,
                'closed_at': False,
            })
        return super(DriverDeliveryPeriod, self).create(vals)

    def write(self, vals):
        # Month/year/company define the accounting period and must not be
        # silently changed after creation. State transitions use explicit
        # buttons below so the audit fields remain reliable.
        protected = {'month_name', 'year', 'company_id', 'state'}
        if protected.intersection(vals) and not self.env.context.get('period_control_write'):
            raise ValidationError(_(
                'لا يمكن تعديل الشهر أو السنة أو الشركة أو الحالة مباشرة. '
                'استخدم أزرار فتح/إقفال الفترة.'
            ))
        return super(DriverDeliveryPeriod, self).write(vals)

    def action_open_period(self):
        self._check_manager()
        for rec in self:
            if rec.state == 'open':
                continue
            rec.with_context(period_control_write=True).write({
                'state': 'open',
                'opened_by': self.env.user.id,
                'opened_at': fields.Datetime.now(),
                'closed_by': False,
                'closed_at': False,
            })
        return True

    def action_close_period(self):
        self._check_manager()
        for rec in self:
            if rec.state == 'closed':
                continue
            rec.with_context(period_control_write=True).write({
                'state': 'closed',
                'closed_by': self.env.user.id,
                'closed_at': fields.Datetime.now(),
            })
        return True

    def unlink(self):
        self._check_manager()
        Batch = self.env['trnsp.store.driver.request.batch']
        for rec in self:
            batch_count = Batch.search_count([
                ('company_id', '=', rec.company_id.id),
                ('month_name', '=', rec.month_name),
                ('year', '=', rec.year),
            ])
            if batch_count:
                raise ValidationError(_(
                    'لا يمكن حذف فترة مرتبطة بملفات توصيل سائقين. يمكنك إقفالها بدلاً من الحذف.'
                ))
        return super(DriverDeliveryPeriod, self).unlink()
