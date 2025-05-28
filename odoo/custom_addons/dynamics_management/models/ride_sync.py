# C:\Users\kebic\OneDrive\Desktop\rest_api_v1\odoo-project\odoo\custom_addons\dynamics_management\models\ride_sync.py
from odoo import api, models
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class DynamicsRide(models.Model):
    _inherit = 'dynamics.ride'

    @api.model
    def sync_rides_from_api(self):
        """Synchronize rides from the external API."""
        try:
            api_url = 'http://147.93.52.105:9080/ride'
            _logger.info("Fetching all rides from %s", api_url)
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            _logger.info("API response: Status %s", response.status_code)

            if response.status_code == 200:
                rides = response.json()
                if not isinstance(rides, list):
                    _logger.error("API response is not a list: %s", response.text)
                    raise UserError("API response is not a valid list of rides.")

                synced_rides = 0
                for ride in rides:
                    ride_external_id = str(ride.get('id'))
                    # Skip if ride already exists in Odoo
                    if self.search([('external_id', '=', ride_external_id)], limit=1):
                        _logger.info("Ride with external_id %s already exists, skipping sync to preserve existing values.", ride_external_id)
                        continue

                    line_external_id = ride.get('line')
                    line = self.env['infrastructure.line'].search(
                        [('external_id', '=', line_external_id)], limit=1
                    )
                    if not line:
                        _logger.warning("Line %s not found for ride %s, creating placeholder.", 
                                        line_external_id, ride_external_id)
                        line = self.env['infrastructure.line'].create({
                            'name': f'Line {line_external_id or "Unknown"} (Auto-created)',
                            'external_id': line_external_id or f"temp_{ride_external_id}"
                        })

                    departure_dt = ride.get('departureDatetime')
                    arrival_dt = ride.get('arrivalDatetime')
                    if departure_dt:
                        try:
                            departure_dt = datetime.fromisoformat(departure_dt.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            departure_dt = None
                    if arrival_dt:
                        try:
                            arrival_dt = datetime.fromisoformat(arrival_dt.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            arrival_dt = None

                    direction = ride.get('direction', 'GOING')
                    if direction not in ['GOING', 'RETURNING']:
                        direction = 'GOING'

                    status = ride.get('status', 'IDLE')
                    if status == 'FINISHED':
                        status = 'COMPLETED'
                    if status not in ['ON_GOING', 'COMPLETED', 'CANCELLED', 'IDLE']:
                        status = 'IDLE'

                    ride_data = {
                        'external_id': ride_external_id,
                        'direction': direction,
                        'departure_datetime': departure_dt,
                        'arrival_datetime': arrival_dt,
                        'status': status,
                        'lat': ride.get('lat', 0.0),
                        'lng': ride.get('lng', 0.0),
                        'location_type': ride.get('locationType', 'UNKNOWN'),
                        'location_id': ride.get('locationId'),
                        'passengers': json.dumps(ride.get('passengers', [])),
                        'line_id': line.id,
                        'driver': str(ride.get('driver')) if ride.get('driver') is not None else None,
                        'vehicle': str(ride.get('vehicle')) if ride.get('vehicle') is not None else None,
                        'position_id': None
                    }

                    # Create with sync context to skip POST
                    self.with_context(from_sync=True).create(ride_data)
                    _logger.info("Synced new ride %s.", ride_external_id)
                    synced_rides += 1

                _logger.info("Successfully synced %s new rides.", synced_rides)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Synchronization Completed',
                        'message': f'Successfully synced {synced_rides} new rides from the API.',
                        'type': 'success',
                        'sticky': False,
                    }
                }

            else:
                _logger.error("Failed to fetch rides: %s (Status: %s)", response.text, response.status_code)
                raise UserError(f"Failed to fetch rides: {response.text} (Status: {response.status_code})")

        except requests.RequestException as e:
            _logger.error("API request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except Exception as e:
            _logger.error("Sync failed: %s", str(e))
            raise UserError(f"Failed to sync rides: {str(e)}")

    @api.model
    def get_ride_map_data(self):
        """Fetch ON_GOING ride data for the map view."""
        rides = self.search([('status', '=', 'ON_GOING'), ('lat', '!=', False), ('lng', '!=', False)])
        return [{
            'id': ride.id,
            'external_id': ride.external_id,
            'lat': ride.lat,
            'lng': ride.lng,
            'status': ride.status,
            'direction': ride.direction,
            'location_type': ride.location_type or 'UNKNOWN',
            'departure_datetime': ride.departure_datetime.strftime('%Y-%m-%d %H:%M:%S') if ride.departure_datetime else None,
            'line_name': 'Unknown',  # Placeholder until correct field is identified
            'vehicle_plate': self.env['dynamics.vehicle'].search([('id', '=', int(ride.vehicle))], limit=1).plate_number if ride.vehicle and ride.vehicle.isdigit() else 'Unknown',
        } for ride in rides]