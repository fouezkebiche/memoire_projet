from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class InfrastructureSync(models.Model):
    _name = 'infrastructure.sync'
    _description = 'Infrastructure Synchronization'

    sync_type = fields.Selection([
        ('stations', 'Stations'),
        ('lines', 'Lines'),
        ('line_stations', 'Line Stations'),
    ], string="Sync Type", required=True, default='stations')

    def action_manual_sync(self):
        try:
            if self.sync_type == 'stations':
                result = self.env['infrastructure.station'].sync_infrastructure(sync_stations=True)
            elif self.sync_type == 'lines':
                result = self.env['infrastructure.line'].sync_infrastructure(sync_lines=True)
            elif self.sync_type == 'line_stations':
                result = self.env['infrastructure.line.station'].sync_infrastructure(sync_line_stations=True)
            message = _("Synchronization completed successfully: %s") % result
            _logger.info(message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Success"),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Synchronization failed: %s", str(e))
            raise UserError(_("Synchronization failed: %s") % str(e))