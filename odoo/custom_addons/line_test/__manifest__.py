{
    'name': 'Line test',
    'version': '1.0',
    'summary': 'Manage transport lines from external infrastructure API',
    'author': 'Your Name',
    'category': 'Transport',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/line_management_views.xml',
        'views/line_station_views.xml',
        'views/line_sync_action.xml',
        'views/line_map_action.xml',
        'views/line_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'line_test/static/src/js/line_map.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'line_test/static/src/xml/line_map_templates.xml',
            'line_test/static/src/css/line_map.css',
        ],
    },
    'py_files': [
        'models/line_management.py',
        'models/line_schedule.py',
        'models/line_station.py',  # Include if not already separate
    ],
    'installable': True,
    'application': True,
}