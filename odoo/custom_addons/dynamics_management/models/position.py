from odoo import models, fields

class DynamicsPosition(models.Model):
    _name = 'dynamics.position'
    _description = 'Dynamics Position'

    lat = fields.Float(string='Latitude', digits=(16, 8), required=True)
    lng = fields.Float(string='Longitude', digits=(16, 8), required=True)
    location_type = fields.Selection(
        [('LINE_STATION', 'Line Station'), ('INTER_STATION', 'Inter Station'), ('UNKNOWN', 'Unknown')],
        string='Location Type'
    )
    ride = fields.Many2one('dynamics.ride', string='Ride', required=True)
    timestamp = fields.Datetime(string='Timestamp', required=True)