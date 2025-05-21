from odoo import models, fields, api
from odoo.exceptions import UserError

class InfrastructureSync(models.TransientModel):
    _name = 'infrastructure.sync'
    _description = 'Infrastructure Sync'

    sync_type = fields.Selection(
        [
            ('stations', 'Stations'),
            ('lines', 'Lines'),
            ('line_stations', 'Line Stations'),
        ],
        string='Sync Type',
        required=True,
        default='stations',
        help='Select the type of data to synchronize.'
    )

    def action_manual_sync(self, *args, **kwargs):
        """Trigger manual sync based on selected sync type."""
        try:
            if self.sync_type == 'stations':
                result = self.env['infrastructure.station']._sync_stations_from_api()
                message = f"Stations synchronized: {result['synced']} synced, {result['skipped']} skipped."
            elif self.sync_type == 'lines':
                result = self.env['infrastructure.line']._sync_lines_from_api()
                message = f"Lines synchronized: {result['synced']} synced, {result['skipped']} skipped."
            elif self.sync_type == 'line_stations':
                result = self.env['infrastructure.line.station']._sync_line_stations_from_api()
                message = f"Line Stations synchronized: {result['synced']} synced, {result['skipped']} skipped."
            else:
                raise UserError('Invalid sync type selected.')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Synchronization failed: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }