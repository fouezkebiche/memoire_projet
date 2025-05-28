from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class InfrastructureLine(models.Model):
    _name = 'infrastructure.line'
    _description = 'Infrastructure Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'enterprise_code'

    code = fields.Char(
        string="Code", required=True, tracking=True)
    color = fields.Char(
        string="Color", default='#000000', tracking=True)
    line_type = fields.Selection(
        [('1', 'Type 1'), ('2', 'Type 2')],
        string='Line Type',
        default='1', tracking=True)
    enterprise_code = fields.Char(
        string="Enterprise Code", required=True, tracking=True)
    departure_station_id = fields.Many2one(
        'infrastructure.station',
        string='Departure Station', tracking=True)
    terminus_station_id = fields.Many2one(
        'infrastructure.station',
        string='Terminus Station', tracking=True)
    line_station_ids = fields.One2many(
        'infrastructure.line.station',
        'line_id',
        string='Line Stations', tracking=True)
    schedule = fields.Text(
        string="Schedule", default='[]', tracking=True)
    external_id = fields.Integer(
        string="External ID", index=True, readonly=True)

    def name_get(self):
        result = []
        for line in self:
            name = line.enterprise_code or line.code or f'Line {line.id}'
            _logger.debug("name_get for line ID %s: %s", line.id, name)
            result.append((line.id, name))
        return resultv