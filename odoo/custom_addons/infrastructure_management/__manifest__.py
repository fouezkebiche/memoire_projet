{
    'name': 'Infrastructure Management',
    'version': '1.7',
    'summary': 'Manage transportation lines, stations, and line stations',
    'description': 'A module to manage lines, stations, line stations, and integrate with etrans_infrastructure API.',
    'category': 'Tools',
    'author': 'Your Name',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/line_views.xml',
        'views/line_type_views.xml',
        'views/station_views.xml',
        'views/line_station_views.xml',
        'views/station_map_action.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'infrastructure_management/static/src/js/station_map.js',
            'infrastructure_management/static/src/xml/station_map_templates.xml',
            'infrastructure_management/static/src/css/station_map.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
            'https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.3/umd/popper.min.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}