{
    'name': 'Custom Redirect to Apps',
    'version': '1.0',
    'depends': ['web', 'base'],
    'author': 'kebiche fouez',
    'category': 'Tools',
    'description': 'Redirects to the Apps page on startup and filters apps.',
    'data': [
        'security/ir.model.access.csv',
        'views/module_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}