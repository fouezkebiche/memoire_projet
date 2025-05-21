from odoo import models, fields, api
from odoo.exceptions import UserError

class InfrastructureSyncWizard(models.TransientModel):
    _name = 'infrastructure.sync.wizard'
    _description = 'Infrastructure Sync Wizard'

    sync_stations = fields.Boolean(string='Sync Stations', default=True)
    sync_lines = fields.Boolean(string='Sync Lines', default=True)
    sync_line_stations = fields.Boolean(string='Sync Line Stations', default=True)

    def action_sync(self):
        """Execute the synchronization based on selected options"""
        try:
            station_model = self.env['infrastructure.station']
            result = station_model.sync_infrastructure(
                sync_stations=self.sync_stations,
                sync_lines=self.sync_lines,
                sync_line_stations=self.sync_line_stations
            )
            
            # Prepare message
            message_parts = []
            if self.sync_stations:
                message_parts.append(f"Stations: {result['stations']['synced']} synced, {result['stations']['skipped']} skipped")
            if self.sync_lines:
                message_parts.append(f"Lines: {result['lines']['synced']} synced, {result['lines']['skipped']} skipped")
            if self.sync_line_stations:
                message_parts.append(f"Line Stations: {result['line_stations']['synced']} synced, {result['line_stations']['skipped']} skipped")
            
            message = "\n".join(message_parts)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Complete',
                    'message': message,
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Failed',
                    'message': str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            } 