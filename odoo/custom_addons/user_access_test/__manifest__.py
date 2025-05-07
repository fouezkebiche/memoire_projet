{
    'name': 'User Access Test',
    'version': '1.0',
    'category': 'Test',
    'depends': ['base'],
    'data': [
    'security/security.xml',
    'security/ir.model.access.csv',
    'views/test_item_views.xml',  # ← this is fine now because you have the action defined
    ],

    'installable': True,
    'application': True,
}
