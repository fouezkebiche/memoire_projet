from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class InfrastructureSyncWizard(models.TransientModel):
    _name = 'infrastructure.sync.wizard'
    _description = 'Infrastructure Synchronization Wizard'

    sync_stations = fields.Boolean(string="Sync Stations", default=True)
    sync_lines = fields.Boolean(string="Sync Lines", default=True)
    sync_line_stations = fields.Boolean(string="Sync Line Stations", default=True)

    def action_sync(self):
        try:
            result = {}
            if self.sync_stations:
                result.update(self.env['infrastructure.station'].sync_infrastructure(sync_stations=True))
            if self.sync_lines:
                result.update(self.env['infrastructure.line'].sync_infrastructure(sync_lines=True))
            if self.sync_line_stations:
                result.update(self.env['infrastructure.line.station'].sync_infrastructure(sync_line_stations=True))

            # Prepare message
            message_parts = []
            if 'stations' in result:
                message_parts.append(f"Stations: {result['stations']['created']} created, {result['stations']['updated']} updated, {result['stations']['deleted']} deleted")
            if 'lines' in result:
                message_parts.append(f"Lines: {result['lines']['created']} created, {result['lines']['updated']} updated, {result['lines']['deleted']} deleted")
            if 'line_stations' in result:
                message_parts.append(f"Line Stations: {result['line_stations']['created']} created, {result['line_stations']['updated']} updated, {result['line_stations']['deleted']} deleted")
            
            message = "\n".join(message_parts) or "No synchronization performed."
            
            _logger.info("Synchronization completed: %s", message)
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
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Failed"),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }