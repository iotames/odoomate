# -*- coding: utf-8 -*-
{
    'name': "Git Information",
    'installable': True,
    'application': True,
    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "Hankin",
    'website': "https://github.com/iotames/odoomate",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Odoomate/System',
    'version': '17.0.0.5.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    # 顺序：安全，数据，试图，菜单
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/git_info_views.xml',
        'views/menu.xml',
        # 'views/views.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'LGPL-3',
}

