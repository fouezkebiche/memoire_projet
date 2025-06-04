{
    'name': 'Profiles Management',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage passenger and driver profiles integrated with Ptrans Profile API',
    'description': """
        A module to manage passenger and driver profiles, providing functionalities to view passenger lists and details
        by integrating with the Ptrans Profile API.
    """,
    'author': 'Kebiche fouez',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/profile_passenger_views.xml',
        'views/profile_driver_views.xml',
        'views/profiles_management_menu.xml',
        'views/profile_passenger_cron.xml',
        'views/profile_driver_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'profiles_management/static/src/js/driver_search.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
