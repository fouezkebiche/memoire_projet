from odoo import models, fields

class Bus(models.Model):
    _name = 'bus_tracking.bus'
    _description = 'Bus Tracking'

    name = fields.Char(string='Bus Name', required=True)
    driver = fields.Char(string='Driver')
    latitude = fields.Float(string='Latitude')
    longitude = fields.Float(string='Longitude')
