{
    'name': 'Transport Bus',
    'version': '1.0',
    'depends': ['base'],
    'author': 'kebiche fouez',
    'category': 'Transport',
    'summary': 'Manages buses and their location',
    'description': 'Module to manage buses with GPS tracking',
    'data': [
        'views/bus_views.xml',
        'security/ir.model.access.csv',
        'views/bus_map_template.xml',
    ],
    'controllers': [
        'controllers/transport_bus_controller.py',
    ],
    'installable': True,
    'application': True,
}
