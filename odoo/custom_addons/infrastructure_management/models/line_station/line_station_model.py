from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class InfrastructureLineStation(models.Model):
    _name = 'infrastructure.line.station'
    _description = 'Infrastructure Line Station'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    order = fields.Integer(
        string='Order', required=True, tracking=True)
    stop_duration = fields.Integer(
        string='Stop Duration', default=0, tracking=True)
    direction = fields.Selection(
        [('GOING', 'Going'), ('RETURNING', 'Returning')],
        string='Direction',
        required=True, tracking=True)
    radius = fields.Integer(
        string='Radius', default=0, tracking=True)
    lat = fields.Float(
        string='Latitude', default=0.0, tracking=True)
    lng = fields.Float(
        string='Longitude', default=0.0, tracking=True)
    line_id = fields.Many2one(
        'infrastructure.line',
        string='Line',
        required=True, tracking=True)
    station_id = fields.Many2one(
        'infrastructure.station',
        string='Station',
        required=True, tracking=True)
    alertable = fields.Boolean(
        string='Alertable', default=False, tracking=True)
    efficient = fields.Boolean(
        string='Efficient', default=False, tracking=True)
    duration = fields.Integer(
        string='Duration', default=0, tracking=True)
    external_id = fields.Integer(
        string='External ID', readonly=True, index=True)
    location_picker = fields.Boolean(
        string='Location Picker', default=True)