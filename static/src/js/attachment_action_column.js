odoo.define('qimamhd_transportation_driver_delivery.attachment_action_column', function (require) {
    'use strict';

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        _renderBodyCell: function (record, node, index, options) {
            if (node.tag === 'button' && node.attrs &&
                    node.attrs.name === 'action_manage_trip_sheet_attachment') {
                node = _.extend({}, node, {
                    attrs: _.extend({}, node.attrs, {
                        string: record.data.trip_sheet_image ? 'عرض المرفق' : 'إضافة مرفق',
                        class: record.data.trip_sheet_image
                            ? 'oe_highlight o_driver_delivery_attachment_action'
                            : 'btn-secondary o_driver_delivery_attachment_action'
                    })
                });
            }
            return this._super(record, node, index, options);
        },
    });
});
