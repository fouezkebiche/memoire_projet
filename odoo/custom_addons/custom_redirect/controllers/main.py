from odoo import http
from odoo.http import request

class CustomRedirect(http.Controller):
    @http.route('/', type='http', auth='user')
    def redirect_to_apps(self, **kw):
        # Redirect to the Apps page using the correct action ID
        return request.redirect('/web#action=base.open_module_tree')