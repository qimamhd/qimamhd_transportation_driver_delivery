# -*- coding: utf-8 -*-
{
    'name': 'QimamHD Transportation Driver Delivery',
<<<<<<< HEAD
    'version': '13.0.4.10.30',
=======
    'version': '13.0.4.10.29',
>>>>>>> d661dedd449f996beaaea3b98d88f8e74f6842a7
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
        'data/driver_app_cron.xml',
        'views/hr_employee_driver_app_views.xml',
        'views/res_company_driver_app_views.xml',
        'views/store_driver_pricing_gps_views.xml',
        'views/delivery_period_views.xml',
        'views/store_driver_request_views.xml',
        'views/exception_accept_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
