from odoo import models, fields, api, _
import json

class InfrastructureStation(models.Model):
    _name = 'infrastructure.station'
    _description = 'Infrastructure Station'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name_en'

    name_ar = fields.Char(
        string="Name (Arabic)", required=True, tracking=True)
    name_en = fields.Char(
        string="Name (English)", required=True, tracking=True)
    name_fr = fields.Char(
        string="Name (French)", required=True, tracking=True)
    latitude = fields.Float(
        string="Latitude", digits=(9, 6), default=36.7538, tracking=True)
    longitude = fields.Float(
        string="Longitude", digits=(9, 6), default=3.0588, tracking=True)
    line_ids = fields.Many2many(
        'infrastructure.line', string="Lines", tracking=True)
    paths = fields.Text(
        string="Paths", default='[]', tracking=True)
    changes = fields.Text(
        string="Changes", default='{}', tracking=True)
    schedule = fields.Text(
        string="Schedule", default='[]', tracking=True)
    external_id = fields.Integer(
        string="External ID", index=True, readonly=True)
    location_picker = fields.Boolean(string='Location Picker', default=True)

    