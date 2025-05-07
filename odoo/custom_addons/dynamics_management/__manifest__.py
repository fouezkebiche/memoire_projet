{
    'name': 'Dynamics Management',
    'version': '1.0',
    'summary': 'Manage rides and their positions',
    'description': 'A module to manage rides, their positions, and integrate with the Dynamics API.',
    'category': 'Tools',
    'author': 'Your Name',
    'depends': ['base', 'web', 'infrastructure_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/ride_views.xml',
        'views/ride_map_action.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamics_management/static/src/js/ride_map.js',
            'dynamics_management/static/src/xml/ride_map_templates.xml',
            'dynamics_management/static/src/css/ride_map.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}