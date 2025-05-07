from odoo import models, fields

class TransportBus(models.Model):
    _name = 'transport.bus'
    _description = 'Bus'

    bus_number = fields.Char(string='Bus Number', required=True)
    driver = fields.Char(string='Driver Name')
    latitude = fields.Float(string='Latitude')
    longitude = fields.Float(string='Longitude')
    active = fields.Boolean(string='Active', default=True)
