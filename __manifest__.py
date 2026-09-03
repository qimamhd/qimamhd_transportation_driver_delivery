# -*- coding: utf-8 -*-
{
    'name': 'QimamHD Transportation Driver Delivery',
    'version': '13.0.4.6.1',
    'summary': 'Driver app access and monthly restaurant delivery review before settlement',
    'category': 'Transportation',
    'author': 'QimamHD',
    'license': 'LGPL-3',
    'depends': [
        'qimamhd_transportation_v2_13',
    ],
    'data': [
        'security/driver_delivery_security.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_driver_app_views.xml',
        'views/store_driver_pricing_gps_views.xml',
        'views/delivery_period_views.xml',
        'views/store_driver_request_views.xml',
        'views/exception_accept_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
