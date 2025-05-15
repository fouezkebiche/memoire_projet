from odoo import models, api

class InfrastructureSync(models.TransientModel):
    _name = 'infrastructure.sync'
    _description = 'Infrastructure Sync'

    def action_manual_sync(self, *args, **kwargs):
        """Trigger manual sync for Stations, Lines, and Line Stations."""
        try:
            # Sync Stations first
            self.env['infrastructure.station'].sync_stations_from_api()
            # Sync Lines (depends on Stations)
            self.env['infrastructure.line'].sync_lines_from_api()
            # Sync Line Stations (depends on Lines and Stations)
            self.env['infrastructure.line.station'].sync_linestations_from_api()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Manual synchronization completed successfully.',
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
                    'message': f'Manual synchronization failed: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }