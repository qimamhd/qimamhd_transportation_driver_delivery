# -*- coding: utf-8 -*-

import math
import re
import uuid
import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class TrnspStorePricingLines(models.Model):
    _inherit = 'trnsp.store.pricing.lines'

    gps_radius = fields.Float(
        string='مجال GPS المسموح (متر)',
        default=200.0,
        help='أقصى مسافة مسموحة بين موقع السائق وموقع الوجهة عند تسجيل التوصيلة.'
    )

    @api.constrains('gps_radius')
    def _check_gps_radius(self):
        for rec in self:
            if rec.gps_radius < 0:
                raise ValidationError(
                    _('مجال GPS لا يمكن أن يكون قيمة سالبة.')
                )


class StoreDriverRequestBatch(models.Model):
    _name = 'trnsp.store.driver.request.batch'
    _description = 'طلبات تطبيق السائقين الشهرية'
    _inherit = ['mail.thread']
    _order = 'year desc, month_name desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='رقم الملف',
        copy=False,
        readonly=True,
        default='/',
        track_visibility='onchange'
    )

    driver_id = fields.Many2one(
        'hr.employee',
        string='السائق',
        domain=[('driver_emp', '=', True)],
        required=True,
        track_visibility='onchange'
    )

    month_name = fields.Selection([
        ('01', 'يناير'),
        ('02', 'فبراير'),
        ('03', 'مارس'),
        ('04', 'ابريل'),
        ('05', 'مايو'),
        ('06', 'يونيو'),
        ('07', 'يوليو'),
        ('08', 'اغسطس'),
        ('09', 'سبتمبر'),
        ('10', 'اكتوبر'),
        ('11', 'نوفمبر'),
        ('12', 'ديسمبر'),
    ], string='الشهر', required=True, track_visibility='onchange')

    year = fields.Integer(
        string='السنة',
        required=True,
        default=lambda self: fields.Date.today().year,
        track_visibility='onchange'
    )

    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        required=True,
        readonly=True,
        default=lambda self: self.env.user.company_id
    )

    branch_id = fields.Many2one(
        'custom.branches',
        string='الفرع',
        required=True,
        readonly=True,
        default=lambda self: self.env.user.branch_id.id
    )

    request_lines = fields.One2many(
        'trnsp.store.driver.request.line',
        'batch_id',
        string='التوصيلات'
    )

    state = fields.Selection([
        ('draft', 'مفتوح لاستقبال الطلبات'),
        ('done', 'مكتمل من السائق'),
        ('review', 'قيد المراجعة'),
        ('approved', 'معتمد'),
        ('transferred', 'تم التحويل للحسبة'),
        ('cancel', 'ملغي'),
    ], string='الحالة',
        default='draft',
        required=True,
        readonly=True,
        track_visibility='onchange'
    )

    line_count = fields.Integer(
        string='عدد التوصيلات',
        compute='_compute_counts'
    )
    gps_valid_count = fields.Integer(
        string='GPS صحيح',
        compute='_compute_counts'
    )
    gps_invalid_count = fields.Integer(
        string='GPS غير صحيح',
        compute='_compute_counts'
    )
    accepted_count = fields.Integer(
        string='المقبولة',
        compute='_compute_counts'
    )
    rejected_count = fields.Integer(
        string='المرفوضة',
        compute='_compute_counts'
    )
    pending_count = fields.Integer(
        string='بانتظار المراجعة',
        compute='_compute_counts'
    )

    review_user_id = fields.Many2one(
        'res.users',
        string='تمت المراجعة بواسطة',
        readonly=True,
        track_visibility='onchange'
    )
    review_date = fields.Datetime(
        string='تاريخ بدء المراجعة',
        readonly=True
    )
    approve_user_id = fields.Many2one(
        'res.users',
        string='تم الاعتماد بواسطة',
        readonly=True,
        track_visibility='onchange'
    )
    approve_date = fields.Datetime(
        string='تاريخ الاعتماد',
        readonly=True
    )
    transfer_date = fields.Datetime(
        string='تاريخ التحويل للحسبة',
        readonly=True
    )
    notes = fields.Text(
        string='ملاحظات الإدارة'
    )

    _sql_constraints = [
        (
            'driver_month_year_company_uniq',
            'unique(driver_id, month_name, year, company_id)',
            'تنبيه: يوجد ملف طلبات لنفس السائق ونفس الشهر والسنة مسبقاً.'
        ),
    ]

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(
                    _('السنة غير صحيحة.')
                )

    def _check_manager(self):
        if not self.env.user.has_group(
            'qimamhd_transportation_driver_delivery.group_driver_request_manager'
        ):
            raise AccessError(
                _('ليس لديك صلاحية مدير طلبات تطبيق السائقين لتنفيذ هذه العملية.')
            )

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'trnsp.store.driver.request.batch'
            ) or '/'
        return super(StoreDriverRequestBatch, self).create(vals)

    @api.depends(
        'request_lines',
        'request_lines.gps_valid',
        'request_lines.review_state'
    )
    def _compute_counts(self):
        for rec in self:
            lines = rec.request_lines
            rec.line_count = len(lines)
            rec.gps_valid_count = len(lines.filtered(lambda x: x.gps_valid))
            rec.gps_invalid_count = len(lines.filtered(lambda x: not x.gps_valid))
            rec.accepted_count = len(lines.filtered(
                lambda x: x.review_state == 'accepted'
            ))
            rec.rejected_count = len(lines.filtered(
                lambda x: x.review_state == 'rejected'
            ))
            rec.pending_count = len(lines.filtered(
                lambda x: x.review_state == 'pending'
            ))

    def action_mark_done(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(
                    _('يمكن إكمال الطلب فقط عندما يكون مفتوحاً.')
                )
            if not rec.request_lines:
                raise ValidationError(
                    _('لا يمكن إكمال ملف لا يحتوي على توصيلات.')
                )
            rec.write({'state': 'done'})

    def action_start_review(self):
        for rec in self:
            if rec.state not in ('draft', 'done'):
                raise ValidationError(
                    _('لا يمكن بدء المراجعة في الحالة الحالية.')
                )
            if not rec.request_lines:
                raise ValidationError(
                    _('لا توجد توصيلات للمراجعة.')
                )
            rec.write({
                'state': 'review',
                'review_user_id': self.env.user.id,
                'review_date': fields.Datetime.now(),
            })

    def action_accept_all(self):
        for rec in self:
            if rec.state != 'review':
                raise ValidationError(
                    _('قبول السطور متاح فقط أثناء المراجعة.')
                )

            invalid = rec.request_lines.filtered(
                lambda x: not x.gps_valid
            )
            if invalid:
                raise ValidationError(
                    _(
                        'يوجد %s توصيلة خارج نطاق GPS أو بدون إعداد GPS. '
                        'راجعها قبل القبول.'
                    ) % len(invalid)
                )

            rec.request_lines.filtered(
                lambda x: x.review_state == 'pending'
            ).write({
                'review_state': 'accepted',
                'reject_reason': False,
            })

    def action_approve(self):
        for rec in self:
            if rec.state != 'review':
                raise ValidationError(
                    _('يجب أن يكون الطلب قيد المراجعة أولاً.')
                )

            if not rec.request_lines:
                raise ValidationError(
                    _('لا توجد توصيلات لاعتمادها.')
                )

            pending = rec.request_lines.filtered(
                lambda x: x.review_state == 'pending'
            )
            if pending:
                raise ValidationError(
                    _('يوجد %s توصيلة لم تتم مراجعتها بعد.') % len(pending)
                )

            accepted = rec.request_lines.filtered(
                lambda x: x.review_state == 'accepted'
            )
            if not accepted:
                raise ValidationError(
                    _('لا توجد أي توصيلة مقبولة لاعتماد الطلب.')
                )

            invalid_accepted = accepted.filtered(
                lambda x: not x.gps_valid
            )
            if invalid_accepted:
                raise ValidationError(
                    _(
                        'لا يمكن اعتماد الملف لأن %s توصيلة مقبولة '
                        'خارج نطاق GPS أو بدون إعداد GPS.'
                    ) % len(invalid_accepted)
                )

            rejected_without_reason = rec.request_lines.filtered(
                lambda x: x.review_state == 'rejected'
                and not x.reject_reason
            )
            if rejected_without_reason:
                raise ValidationError(
                    _('يجب إدخال سبب الرفض لجميع التوصيلات المرفوضة.')
                )

            rec.write({
                'state': 'approved',
                'approve_user_id': self.env.user.id,
                'approve_date': fields.Datetime.now(),
            })

    def action_transfer_to_settlement(self):
        """Transfer accepted app deliveries to the legacy driver settlement as DRAFT only."""
        self._check_manager()
        Settlement = self.env['trnsp.store.drivers.requests']
        SettlementLine = self.env['trnsp.store.drivers.requests.lines']

        for rec in self:
            if rec.state != 'approved':
                raise ValidationError(
                    _('يمكن التحويل إلى تسوية السائق فقط بعد اعتماد الملف.')
                )

            accepted = rec.request_lines.filtered(
                lambda line: line.review_state == 'accepted'
            )
            if not accepted:
                raise ValidationError(_('لا توجد توصيلات مقبولة للتحويل.'))

            invalid = accepted.filtered(lambda line: not line.gps_valid)
            if invalid:
                raise ValidationError(
                    _('لا يمكن التحويل لأن هناك توصيلة مقبولة خارج نطاق GPS.')
                )

            # Idempotency: only lines that have never been linked are eligible.
            pending_transfer = accepted.filtered(
                lambda line: not line.transferred
                and not line.settlement_id
                and not line.settlement_line_id
            )
            inconsistent = accepted.filtered(
                lambda line: (line.transferred or line.settlement_id or line.settlement_line_id)
                and not (line.transferred and line.settlement_id and line.settlement_line_id)
            )
            if inconsistent:
                raise ValidationError(
                    _('توجد توصيلات بحالة تحويل غير مكتملة. أوقف التحويل وراجع البيانات قبل المتابعة.')
                )

            if not pending_transfer:
                # Defensive idempotency if the header state was changed externally.
                rec.write({
                    'state': 'transferred',
                    'transfer_date': rec.transfer_date or fields.Datetime.now(),
                })
                continue

            # The legacy settlement header has one car and one source and its SQL
            # constraint allows only one active settlement per driver/month/state.
            # Never guess how to split incompatible deliveries.
            combos = set(
                (line.product_car_id.id, line.source_path_id.id)
                for line in pending_transfer
            )
            if len(combos) != 1:
                raise ValidationError(
                    _(
                        'التوصيلات المقبولة تحتوي على أكثر من سيارة أو أكثر من مسار شحن. '
                        'شاشة تسوية السائق الحالية لا تسمح بتحويلها بأمان في ملف واحد. '
                        'لم يتم إنشاء أي تسوية.'
                    )
                )

            car_id, source_id = next(iter(combos))
            month_no = int(rec.month_name)
            last_day = calendar.monthrange(rec.year, month_no)[1]
            from_date = date(rec.year, month_no, 1)
            to_date = date(rec.year, month_no, last_day)

            # Detect any existing non-cancelled settlement for this driver/month.
            # Reuse it only when it is still draft and matches car/source.
            existing = Settlement.search([
                ('driver_id', '=', rec.driver_id.id),
                ('to_date', '=', fields.Date.to_string(to_date)),
                ('state', '!=', 'cancel'),
            ])
            if len(existing) > 1:
                raise ValidationError(
                    _('يوجد أكثر من كشف تسوية فعال لنفس السائق والشهر. لم يتم التحويل.')
                )

            if existing:
                settlement = existing[0]
                if settlement.state != 'draft':
                    raise ValidationError(
                        _('توجد تسوية سابقة لنفس السائق والشهر وليست مسودة. لم يتم تعديلها.')
                    )
                if (
                    settlement.product_car_id.id != car_id
                    or settlement.source_path_id.id != source_id
                ):
                    raise ValidationError(
                        _(
                            'توجد تسوية مسودة لنفس السائق والشهر ولكن بسيارة أو مسار شحن مختلف. '
                            'لم يتم تعديل التسوية الحالية.'
                        )
                    )
            else:
                # The legacy create() reads vals['seq'] before super(), therefore
                # provide it explicitly to avoid a KeyError in programmatic creation.
                settlement = Settlement.create({
                    'seq': Settlement._get_sequence(),
                    'driver_id': rec.driver_id.id,
                    'product_car_id': car_id,
                    'source_path_id': source_id,
                    'from_date': fields.Date.to_string(from_date),
                    'to_date': fields.Date.to_string(to_date),
                    'month_name': rec.month_name,
                    'company_id': rec.company_id.id,
                    'branch_id': rec.branch_id.id,
                    'state': 'draft',
                })

            # Group only this batch's untransferred accepted deliveries by destination.
            destinations = {}
            for line in pending_transfer:
                destinations.setdefault(line.destination_path_id.id, self.env['trnsp.store.driver.request.line'])
                destinations[line.destination_path_id.id] |= line

            for destination_id, source_lines in destinations.items():
                pricing_lines = source_lines.mapped('pricing_line_id')
                if not pricing_lines or len(pricing_lines) != 1:
                    raise ValidationError(
                        _('تعذر تحديد تسعيرة واحدة للوجهة أثناء التحويل. لم يتم التحويل.')
                    )
                pricing = pricing_lines[0]
                if (
                    pricing.destination_path_id.id != destination_id
                    or pricing.header_id.source_path_id.id != source_id
                ):
                    raise ValidationError(
                        _('إعداد التسعير لا يطابق مسار الشحن والوجهة. لم يتم التحويل.')
                    )

                qty = len(source_lines)
                settlement_line = SettlementLine.search([
                    ('header_id', '=', settlement.id),
                    ('product_car_id', '=', car_id),
                    ('destination_path_id', '=', destination_id),
                ], limit=1)

                distance_km = pricing.distination_km or 0.0
                km_driven = qty * distance_km
                km_diesel = rec.branch_id.km_diesel or 0.0
                diesel = (km_driven / km_diesel) if km_diesel else 0.0

                if settlement_line:
                    new_qty = settlement_line.quantity + qty
                    new_km_driven = new_qty * distance_km
                    new_diesel = (new_km_driven / km_diesel) if km_diesel else 0.0
                    settlement_line.write({
                        'quantity': new_qty,
                        'distination_km': distance_km,
                        'km_price': pricing.price or 0.0,
                        'delivered_price': pricing.delivered_price or 0.0,
                        'km_driven': new_km_driven,
                        'diesel_fuel_consum': new_diesel,
                    })
                else:
                    settlement_line = SettlementLine.create({
                        'header_id': settlement.id,
                        'product_car_id': car_id,
                        'destination_path_id': destination_id,
                        'quantity': qty,
                        'distination_km': distance_km,
                        'km_price': pricing.price or 0.0,
                        'delivered_price': pricing.delivered_price or 0.0,
                        'km_driven': km_driven,
                        'diesel_fuel_consum': diesel,
                    })

                source_lines.write({
                    'settlement_id': settlement.id,
                    'settlement_line_id': settlement_line.id,
                    'transferred': True,
                })

            # Do not call confirm_btn or any accounting action. The accountant
            # receives a normal legacy settlement in DRAFT and continues manually.
            rec.write({
                'state': 'transferred',
                'transfer_date': fields.Datetime.now(),
            })

        return True

    def action_reopen(self):
        self._check_manager()
        for rec in self:
            if rec.state not in ('done', 'review', 'approved'):
                raise ValidationError(
                    _('لا يمكن إعادة فتح الطلب في الحالة الحالية.')
                )

            # Any previous review becomes invalid once the file is reopened.
            rec.request_lines.with_context(
                driver_delivery_workflow_write=True
            ).write({
                'review_state': 'pending',
                'reject_reason': False,
            })

            rec.write({
                'state': 'draft',
                'review_user_id': False,
                'review_date': False,
                'approve_user_id': False,
                'approve_date': False,
            })

    def action_cancel(self):
        self._check_manager()
        for rec in self:
            if rec.state == 'transferred':
                raise ValidationError(
                    _('لا يمكن إلغاء طلب تم تحويله للحسبة.')
                )
            rec.write({'state': 'cancel'})

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(
                    _('يمكن حذف الطلب فقط عندما يكون مفتوحاً.')
                )
        return super(StoreDriverRequestBatch, self).unlink()


class StoreDriverRequestLine(models.Model):
    _name = 'trnsp.store.driver.request.line'
    _description = 'تفاصيل توصيلات تطبيق السائق'
    _order = 'request_date desc, request_time desc, id desc'

    batch_id = fields.Many2one(
        'trnsp.store.driver.request.batch',
        string='ملف السائق',
        required=True,
        ondelete='cascade',
        index=True
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='السائق',
        related='batch_id.driver_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        related='batch_id.company_id',
        store=True,
        readonly=True
    )
    month_name = fields.Selection(
        related='batch_id.month_name',
        store=True,
        readonly=True
    )
    year = fields.Integer(
        related='batch_id.year',
        store=True,
        readonly=True
    )

    mobile_uuid = fields.Char(
        string='UUID التطبيق',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: str(uuid.uuid4()),
        index=True
    )
    request_date = fields.Date(
        string='التاريخ',
        required=True,
        default=fields.Date.context_today
    )
    request_time = fields.Char(
        string='الوقت',
        required=True,
        help='الوقت بصيغة HH:MM:SS'
    )
    server_received_at = fields.Datetime(
        string='وقت وصول الطلب للسيرفر',
        default=fields.Datetime.now,
        readonly=True
    )

    product_car_id = fields.Many2one(
        'product.product',
        string='السيارة',
        domain="[('car_flag','=',True)]",
        required=True
    )
    source_path_ids = fields.Many2many(
        'trnsp.cars.areas',
        compute='_compute_source_path_ids',
        string='مصادر الشحن المسموحة'
    )
    source_path_id = fields.Many2one(
        'trnsp.cars.areas',
        string='مسار الشحن (المصدر)',
        required=True,
        domain=lambda self: [
            ('id', 'in',
             self.env['trnsp.store.pricing'].sudo().search([
                 ('source_path_id', '!=', False)
             ]).mapped('source_path_id').ids)
        ]
    )
    destination_path_ids = fields.Many2many(
        'trnsp.store.areas',
        compute='_compute_destination_path_ids',
        string='الوجهات المسموحة'
    )
    destination_path_id = fields.Many2one(
        'trnsp.store.areas',
        string='الوجهة',
        required=True
    )
    pricing_line_id = fields.Many2one(
        'trnsp.store.pricing.lines',
        string='إعداد المسار',
        readonly=True
    )

    driver_latitude = fields.Float(
        string='Latitude السائق',
        digits=(16, 7),
        required=True
    )
    driver_longitude = fields.Float(
        string='Longitude السائق',
        digits=(16, 7),
        required=True
    )
    destination_latitude = fields.Float(
        string='Latitude الوجهة',
        digits=(16, 7),
        readonly=True
    )
    destination_longitude = fields.Float(
        string='Longitude الوجهة',
        digits=(16, 7),
        readonly=True
    )
    allowed_radius = fields.Float(
        string='النطاق المسموح (متر)',
        readonly=True
    )
    gps_distance = fields.Float(
        string='البعد عن الوجهة (متر)',
        readonly=True
    )
    gps_valid = fields.Boolean(
        string='داخل نطاق GPS',
        readonly=True
    )

    review_state = fields.Selection([
        ('pending', 'بانتظار المراجعة'),
        ('accepted', 'مقبول'),
        ('rejected', 'مرفوض'),
    ], string='نتيجة المراجعة',
        default='pending',
        required=True
    )

    @api.onchange('review_state')
    def _onchange_review_state_gps_guard(self):
        for rec in self:
            if rec.review_state == 'accepted' and not rec.gps_valid:
                rec.review_state = 'pending'
                return {
                    'warning': {
                        'title': _('لا يمكن قبول التوصيلة'),
                        'message': _(
                            'هذه التوصيلة خارج نطاق GPS أو لا تحتوي على إعداد GPS صالح. '
                            'يجب رفضها أو تصحيح بيانات الموقع قبل قبولها.'
                        ),
                    }
                }

    @api.constrains('review_state', 'gps_valid')
    def _check_accepted_requires_valid_gps(self):
        for rec in self:
            if rec.review_state == 'accepted' and not rec.gps_valid:
                raise ValidationError(
                    _(
                        'لا يمكن حفظ التوصيلة كمقبولة لأنها خارج نطاق GPS '
                        'أو بدون إعداد GPS صالح.'
                    )
                )

    def _check_reviewer_access(self):
        if not self.env.user.has_group(
            'qimamhd_transportation_driver_delivery.group_driver_request_reviewer'
        ):
            raise AccessError(
                _('ليس لديك صلاحية مراجعة طلبات تطبيق السائقين.')
            )

    def action_accept_line(self):
        self._check_reviewer_access()
        for rec in self:
            if rec.batch_id.state != 'review':
                raise ValidationError(
                    _('يمكن قبول التوصيلة فقط أثناء حالة قيد المراجعة.')
                )
            if not rec.gps_valid:
                raise ValidationError(
                    _(
                        'لا يمكن قبول هذه التوصيلة لأن موقع السائق خارج نطاق GPS '
                        'المسموح أو لأن إعداد GPS للوجهة غير صالح.'
                    )
                )
            rec.with_context(driver_delivery_workflow_write=True).write({
                'review_state': 'accepted',
                'reject_reason': False,
            })
        return True

    def action_reject_line(self):
        self._check_reviewer_access()
        for rec in self:
            if rec.batch_id.state != 'review':
                raise ValidationError(
                    _('يمكن رفض التوصيلة فقط أثناء حالة قيد المراجعة.')
                )
            rec.with_context(driver_delivery_workflow_write=True).write({
                'review_state': 'rejected',
            })
        return True

    def action_reset_review_line(self):
        self._check_reviewer_access()
        for rec in self:
            if rec.batch_id.state != 'review':
                raise ValidationError(
                    _('يمكن إعادة التوصيلة للمراجعة فقط أثناء حالة قيد المراجعة.')
                )
            rec.with_context(driver_delivery_workflow_write=True).write({
                'review_state': 'pending',
                'reject_reason': False,
            })
        return True
    reject_reason = fields.Char(
        string='سبب الرفض'
    )
    notes = fields.Char(
        string='ملاحظات السائق'
    )
    admin_notes = fields.Char(
        string='ملاحظات الإدارة'
    )

    settlement_id = fields.Many2one(
        'trnsp.store.drivers.requests',
        string='كشف الحسبة',
        readonly=True,
        copy=False
    )
    settlement_line_id = fields.Many2one(
        'trnsp.store.drivers.requests.lines',
        string='سطر الحسبة',
        readonly=True,
        copy=False
    )
    transferred = fields.Boolean(
        string='تم التحويل للحسبة',
        readonly=True,
        copy=False,
        default=False
    )

    _sql_constraints = [
        (
            'mobile_uuid_uniq',
            'unique(mobile_uuid)',
            'تنبيه: هذه التوصيلة تم إرسالها مسبقاً من التطبيق.'
        ),
    ]

    def _compute_source_path_ids(self):
        pricing = self.env['trnsp.store.pricing'].sudo().search([
            ('source_path_id', '!=', False)
        ])
        allowed_source_ids = pricing.mapped('source_path_id').ids
        for rec in self:
            rec.source_path_ids = [(6, 0, allowed_source_ids)]

    @api.depends('source_path_id')
    def _compute_destination_path_ids(self):
        for rec in self:
            if not rec.source_path_id:
                rec.destination_path_ids = False
                continue

            pricing = self.env['trnsp.store.pricing'].sudo().search([
                ('source_path_id', '=', rec.source_path_id.id)
            ])

            rec.destination_path_ids = (
                pricing.mapped('pricing_lines.destination_path_id').ids
                if pricing else False
            )

    @api.onchange('source_path_id')
    def _onchange_source_path_id(self):
        self.destination_path_id = False
        self.pricing_line_id = False
        self.destination_latitude = 0.0
        self.destination_longitude = 0.0
        self.allowed_radius = 0.0
        self.gps_distance = 0.0
        self.gps_valid = False

        source_ids = self.env['trnsp.store.pricing'].sudo().search([
            ('source_path_id', '!=', False)
        ]).mapped('source_path_id').ids

        destination_ids = []
        if self.source_path_id:
            pricing = self.env['trnsp.store.pricing'].sudo().search([
                ('source_path_id', '=', self.source_path_id.id)
            ])
            destination_ids = pricing.mapped(
                'pricing_lines.destination_path_id'
            ).ids

        return {
            'domain': {
                'source_path_id': [('id', 'in', source_ids)],
                'destination_path_id': [('id', 'in', destination_ids)],
            }
        }

    @api.onchange('product_car_id', 'batch_id')
    def _onchange_available_source_paths(self):
        source_ids = self.env['trnsp.store.pricing'].sudo().search([
            ('source_path_id', '!=', False)
        ]).mapped('source_path_id').ids

        if self.source_path_id and self.source_path_id.id not in source_ids:
            self.source_path_id = False
            self.destination_path_id = False

        return {
            'domain': {
                'source_path_id': [('id', 'in', source_ids)],
            }
        }

    @api.onchange('source_path_id', 'destination_path_id')
    def _onchange_destination_path_id(self):
        for rec in self:
            rec._load_destination_gps()
            rec._calculate_gps()

    def _load_destination_gps(self):
        for rec in self:
            rec.pricing_line_id = False
            rec.destination_latitude = 0.0
            rec.destination_longitude = 0.0
            rec.allowed_radius = 0.0

            if not rec.source_path_id or not rec.destination_path_id:
                continue

            pricing_line = self.env['trnsp.store.pricing.lines'].sudo().search([
                ('header_id.source_path_id', '=', rec.source_path_id.id),
                ('destination_path_id', '=', rec.destination_path_id.id),
            ], limit=1)

            if not pricing_line:
                continue

            rec.pricing_line_id = pricing_line.id

            # Preserve legacy fields and their existing data.
            # Business mapping confirmed for this module:
            # gbs_from -> destination latitude
            # gbs_to   -> destination longitude
            rec.destination_latitude = pricing_line.gbs_from
            rec.destination_longitude = pricing_line.gbs_to
            rec.allowed_radius = pricing_line.gps_radius

    @api.onchange(
        'driver_latitude',
        'driver_longitude',
        'destination_latitude',
        'destination_longitude',
        'allowed_radius'
    )
    def _onchange_driver_gps(self):
        for rec in self:
            rec._calculate_gps()

    def _calculate_gps(self):
        for rec in self:
            rec.gps_distance = 0.0
            rec.gps_valid = False

            if (
                not rec.driver_latitude
                or not rec.driver_longitude
                or not rec.destination_latitude
                or not rec.destination_longitude
            ):
                continue

            if not (
                -90.0 <= rec.driver_latitude <= 90.0
                and -180.0 <= rec.driver_longitude <= 180.0
                and -90.0 <= rec.destination_latitude <= 90.0
                and -180.0 <= rec.destination_longitude <= 180.0
            ):
                continue

            distance = rec._distance_meters(
                rec.driver_latitude,
                rec.driver_longitude,
                rec.destination_latitude,
                rec.destination_longitude
            )

            rec.gps_distance = distance
            rec.gps_valid = (
                rec.allowed_radius > 0
                and distance <= rec.allowed_radius
            )

    @api.model
    def _distance_meters(self, lat1, lon1, lat2, lon2):
        radius = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(
            math.sqrt(a),
            math.sqrt(1.0 - a)
        )
        return radius * c

    @api.model
    def _normalize_request_time_value(self, value):
        if not value or not isinstance(value, str):
            return value
        value = value.strip()
        match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', value)
        if not match:
            return value
        hour, minute, second = match.groups()
        normalized = '%02d:%s' % (int(hour), minute)
        if second is not None:
            normalized += ':' + second
        return normalized

    @api.constrains('request_time')
    def _check_request_time(self):
        time_pattern = re.compile(
            r'^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$'
        )
        for rec in self:
            if rec.request_time and not time_pattern.match(rec.request_time):
                raise ValidationError(
                    _('صيغة الوقت غير صحيحة. استخدم HH:MM أو HH:MM:SS.')
                )

    @api.constrains('driver_latitude', 'driver_longitude')
    def _check_driver_coordinates(self):
        for rec in self:
            if not (-90.0 <= rec.driver_latitude <= 90.0):
                raise ValidationError(
                    _('Latitude السائق يجب أن يكون بين -90 و 90.')
                )
            if not (-180.0 <= rec.driver_longitude <= 180.0):
                raise ValidationError(
                    _('Longitude السائق يجب أن يكون بين -180 و 180.')
                )

    @api.constrains(
        'request_date',
        'batch_id',
        'source_path_id',
        'destination_path_id'
    )
    def _check_line_period_and_route(self):
        for rec in self:
            if rec.request_date and rec.batch_id:
                request_month = '%02d' % rec.request_date.month
                request_year = rec.request_date.year

                if request_month != rec.batch_id.month_name:
                    raise ValidationError(
                        _('تاريخ التوصيلة لا ينتمي إلى الشهر المحدد في ملف السائق.')
                    )
                if request_year != rec.batch_id.year:
                    raise ValidationError(
                        _('تاريخ التوصيلة لا ينتمي إلى السنة المحددة في ملف السائق.')
                    )

            if rec.source_path_id:
                pricing_header = self.env['trnsp.store.pricing'].sudo().search([
                    ('source_path_id', '=', rec.source_path_id.id)
                ], limit=1)
                if not pricing_header:
                    raise ValidationError(
                        _('مصدر الشحن المحدد غير موجود في شاشة التسعيرات.')
                    )

            if rec.source_path_id and rec.destination_path_id:
                pricing_line = self.env['trnsp.store.pricing.lines'].sudo().search([
                    ('header_id.source_path_id', '=', rec.source_path_id.id),
                    ('destination_path_id', '=', rec.destination_path_id.id),
                ], limit=1)

                if not pricing_line:
                    raise ValidationError(
                        _('الوجهة المحددة غير مرتبطة بمصدر الشحن المحدد في شاشة التسعيرات.')
                    )

    @api.model
    def create(self, vals):
        if vals.get('request_time'):
            vals['request_time'] = self._normalize_request_time_value(vals['request_time'])

        batch = self.env['trnsp.store.driver.request.batch'].browse(
            vals.get('batch_id')
        )

        if batch and batch.state != 'draft':
            raise ValidationError(
                _('لا يمكن إضافة توصيلات جديدة لأن ملف السائق غير مفتوح.')
            )

        rec = super(StoreDriverRequestLine, self).create(vals)
        rec._load_destination_gps()
        rec._calculate_gps()
        return rec

    def write(self, vals):
        if vals.get('request_time'):
            vals['request_time'] = self._normalize_request_time_value(vals['request_time'])

        protected_fields = {
            'request_date',
            'request_time',
            'product_car_id',
            'source_path_id',
            'destination_path_id',
            'driver_latitude',
            'driver_longitude',
            'mobile_uuid',
        }

        if protected_fields.intersection(vals.keys()):
            for rec in self:
                if rec.batch_id.state != 'draft':
                    raise ValidationError(
                        _('لا يمكن تعديل بيانات التوصيلة بعد بدء المراجعة.')
                    )

        review_fields = {'review_state', 'reject_reason'}
        if (
            review_fields.intersection(vals.keys())
            and not self.env.context.get('driver_delivery_workflow_write')
        ):
            for rec in self:
                if rec.batch_id.state != 'review':
                    raise ValidationError(
                        _('نتيجة المراجعة وسبب الرفض يمكن تعديلهما فقط أثناء حالة قيد المراجعة.')
                    )

        if 'admin_notes' in vals:
            for rec in self:
                if rec.batch_id.state not in ('review', 'approved'):
                    raise ValidationError(
                        _('ملاحظات الإدارة يمكن تعديلها فقط أثناء المراجعة أو بعد الاعتماد.')
                    )

        if vals.get('review_state') == 'accepted':
            invalid_gps = self.filtered(lambda rec: not rec.gps_valid)
            if invalid_gps:
                raise ValidationError(
                    _(
                        'لا يمكن قبول توصيلة خارج نطاق GPS أو بدون إعداد GPS. '
                        'ارفض التوصيلة أو صحح إعدادات الموقع أولاً.'
                    )
                )

        if vals.get('review_state') == 'rejected' and not vals.get('reject_reason'):
            # Inline tree may send the reason in a separate write; final approval
            # still enforces it, so do not block the first selection change.
            pass

        result = super(StoreDriverRequestLine, self).write(vals)

        gps_fields = {
            'driver_latitude',
            'driver_longitude',
            'source_path_id',
            'destination_path_id',
        }
        if gps_fields.intersection(vals.keys()):
            self._load_destination_gps()
            self._calculate_gps()

        return result

    def unlink(self):
        for rec in self:
            if rec.batch_id.state != 'draft':
                raise ValidationError(
                    _('لا يمكن حذف التوصيلة بعد بدء المراجعة.')
                )
        return super(StoreDriverRequestLine, self).unlink()
