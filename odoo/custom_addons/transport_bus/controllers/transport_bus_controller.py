from odoo import http
from odoo.http import request
import json

class TransportBusController(http.Controller):

    @http.route('/bus/map', auth='user', website=True)
    def bus_map(self, **kw):
        buses = request.env['transport.bus'].sudo().search([])
        buses_data = [{
            'bus_number': bus.bus_number,
            'driver': bus.driver or "Unknown",  # ✔️ assuming driver is a Char
            'lat': bus.latitude,
            'lon': bus.longitude
        } for bus in buses if bus.latitude and bus.longitude]

        return request.render('transport_bus.bus_map_template', {
            'buses_json': json.dumps(buses_data)
        })
