{
    'name': 'Bus Tracking',
    'version': '1.0',
    'category': 'Transport',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/bus_views.xml',
        'views/map_client_action.xml',
        'views/menu.xml',
    ],
    'qweb': [
        'static/src/xml/map_templates.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "bus_tracking/static/src/js/bus_map_client_action.js",
            'bus_tracking/static/src/css/bus_tracking.css',
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
            "bus_tracking/static/src/xml/map_templates.xml",
        ],
},

    'installable': True,
    'application': True,
}
