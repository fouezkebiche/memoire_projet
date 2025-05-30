{
    'name': 'Infrastructure Management',
    'version': '1.16',  # Incremented from 1.15
    'summary': 'Manage transportation lines, stations, and line stations',
    'description': 'A module to manage lines, stations, line stations, and integrate with etrans_infrastructure API.',
    'category': 'Tools',
    'author': 'kebiche fouez',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/line_views.xml',
        'views/station_views.xml',
        'views/line_station_views.xml',
        'views/menu.xml',
        'views/sync_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js',
            'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
            'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
            'infrastructure_management/static/src/css/station_map.css',
            'infrastructure_management/static/src/css/line_map.css',
            'infrastructure_management/static/src/css/line_station_map.css',
            'infrastructure_management/static/src/js/station_map.js',
            'infrastructure_management/static/src/js/line_map.js',
            'infrastructure_management/static/src/js/line_station_map.js',
            'infrastructure_management/static/src/js/station_location_picker.js',
            'infrastructure_management/static/src/js/line_station_location_picker.js',  # Added
            'infrastructure_management/static/src/xml/station_map_templates.xml',
            'infrastructure_management/static/src/xml/line_map_templates.xml',
            'infrastructure_management/static/src/xml/line_station_map_templates.xml',
            'infrastructure_management/static/src/xml/station_location_picker_templates.xml',
            'infrastructure_management/static/src/xml/line_station_location_picker_templates.xml',  # Added
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}