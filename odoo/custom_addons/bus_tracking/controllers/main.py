from odoo import http
from odoo.http import request

class BusMapController(http.Controller):

    @http.route('/bus_tracking/map', type='http', auth='public', website=True)
    def bus_map_view(self, **kwargs):
        return request.render('bus_tracking.template_bus_map')
