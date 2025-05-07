from odoo import models, fields

class DynamicsVehicle(models.Model):
    _name = 'dynamics.vehicle'
    _description = 'Dynamics Vehicle'

    plate_number = fields.Char(string='Plate Number', required=True)
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
    registration_number = fields.Char(string='Registration Number')
    num_of_seats = fields.Integer(string='Number of Seats')
    vehicle_owner = fields.Many2one('res.partner', string='Vehicle Owner')
    drivers = fields.Text(string='Drivers', default='[]')