{
    'name': 'Dynamics Management',
    'version': '1.0',
    'summary': 'Manage rides, positions, and vehicles with API integration',
    'description': """
        A module to manage rides, their positions, and vehicles in the Dynamics system.
        Features:
        - Synchronize rides with an external API.
        - Display ongoing rides on an interactive map.
        - Manage vehicle and position data.
        - Automatic and manual sync for rides list view.
    """,
    'category': 'Tools',
    'author': 'Your Name',
    'depends': ['base', 'web', 'infrastructure_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/ride_views.xml',
        'views/menu.xml',
        'views/ride_map_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamics_management/static/src/js/ride_map.js',
            'dynamics_management/static/src/js/ride_list_logger.js',
            'dynamics_management/static/src/xml/ride_map_templates.xml',
            'dynamics_management/static/src/xml/ride_list_templates.xml',
            'dynamics_management/static/src/css/ride_map.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}