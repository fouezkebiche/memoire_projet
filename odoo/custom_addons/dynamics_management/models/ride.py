# C:\Users\kebic\OneDrive\Desktop\rest_api_v1\odoo-project\odoo\custom_addons\dynamics_management\models\ride.py
from odoo import fields, models

class DynamicsRide(models.Model):
    """Model for managing rides in the Dynamics system."""
    _name = 'dynamics.ride'
    _description = 'Dynamics Ride'
    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'External ID must be unique.')
    ]

    direction = fields.Selection(
        string='Direction',
        selection=[('GOING', 'Going'), ('RETURNING', 'Returning')],
        required=True
    )
    departure_datetime = fields.Datetime(string='Departure Datetime')
    arrival_datetime = fields.Datetime(string='Arrival Datetime')
    status = fields.Selection(
        string='Status',
        selection=[
            ('ON_GOING', 'On Going'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
            ('IDLE', 'Idle')
        ]
    )
    lat = fields.Float(string='Latitude')
    lng = fields.Float(string='Longitude')
    location_type = fields.Selection(
        string='Location Type',
        selection=[
            ('LINE_STATION', 'Line Station'),
            ('INTER_STATION', 'Inter Station'),
            ('UNKNOWN', 'Unknown')
        ]
    )
    location_id = fields.Integer(string='Location ID')
    passengers = fields.Char(string='Passengers')
    line_id = fields.Many2one(
        comodel_name='infrastructure.line',
        string='Line',
        required=True
    )
    driver = fields.Char(string='Driver')
    vehicle = fields.Char(string='Vehicle')
    position_id = fields.Many2one(
        comodel_name='dynamics.position',
        string='Position'
    )
    external_id = fields.Char(string='External ID', readonly=True)