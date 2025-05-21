from odoo import api, fields, models
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class DynamicsRide(models.Model):
    _name = 'dynamics.ride'
    _description = 'Dynamics Ride'
    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'External ID must be unique.')
    ]

    direction = fields.Selection(
        string='Direction',
        selection=[('GOING', 'Going'), ('RETURNING', 'Returning')],
        required=True
    )
    departure_datetime = fields.Datetime(string='Departure Datetime')
    arrival_datetime = fields.Datetime(string='Arrival Datetime')
    status = fields.Selection(
        string='Status',
        selection=[
            ('ON_GOING', 'On Going'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
            ('IDLE', 'Idle')
        ]
    )
    lat = fields.Float(string='Latitude')
    lng = fields.Float(string='Longitude')
    location_type = fields.Selection(
        string='Location Type',
        selection=[
            ('LINE_STATION', 'Line Station'),
            ('INTER_STATION', 'Inter Station'),
            ('UNKNOWN', 'Unknown')
        ]
    )
    location_id = fields.Integer(string='Location ID')
    passengers = fields.Char(string='Passengers')
    line_id = fields.Many2one(
        comodel_name='infrastructure.line',
        string='Line',
        required=True
    )
    driver = fields.Char(string='Driver')
    vehicle = fields.Char(string='Vehicle')
    position_id = fields.Many2one(
        comodel_name='dynamics.position',
        string='Position'
    )
    external_id = fields.Char(string='External ID', readonly=True)

    def _prepare_api_data(self):
        # Map Odoo status to API status (COMPLETED -> FINISHED)
        api_status = self.status
        if api_status == 'COMPLETED':
            api_status = 'FINISHED'
        elif api_status not in ['ON_GOING', 'CANCELLED', 'IDLE']:
            api_status = 'IDLE'

        return {
            'direction': self.direction,
            'departureDatetime': self.departure_datetime.isoformat() if self.departure_datetime else None,
            'arrivalDatetime': self.arrival_datetime.isoformat() if self.arrival_datetime else None,
            'status': api_status,
            'lat': self.lat or None,
            'lng': self.lng or None,
            'locationType': self.location_type or None,
            'locationId': self.location_id or None,
            'passengers': json.loads(self.passengers) if self.passengers else [],
            'line': int(self.line_id.external_id) if self.line_id.external_id else self.line_id.id,
            'driver': int(self.driver) if self.driver else None,
            'vehicle': int(self.vehicle) if self.vehicle else None
        }

    @api.model
    def create(self, vals):
        if vals.get('passengers'):
            try:
                json.loads(vals['passengers'])
            except json.JSONDecodeError:
                raise UserError("Passengers must be valid JSON (e.g., [1, 2, 3]).")

        # Check for existing ride with same external_id
        if vals.get('external_id'):
            existing_ride = self.search([('external_id', '=', vals['external_id'])], limit=1)
            if existing_ride:
                _logger.info("Ride with external_id %s already exists, updating instead.", vals['external_id'])
                existing_ride.write(vals)
                return existing_ride

        # Create record locally
        record = super(DynamicsRide, self).create(vals)

        # Skip POST request if in sync context
        if self.env.context.get('from_sync'):
            return record

        # POST to API for manual creation
        api_url = 'http://147.93.52.105:9080/ride'
        api_data = record._prepare_api_data()
        for attempt in range(2):
            try:
                payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
                _logger.info("Sending POST request (attempt %s) to: %s with payload: %s", attempt + 1, api_url, payload.decode('utf-8'))
                response = requests.post(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload,
                    timeout=10
                )
                _logger.info("API POST %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                if response.status_code == 201:
                    try:
                        response_data = response.json()
                        # Map API response to Odoo fields, preserving form inputs for problematic fields
                        update_vals = {
                            'external_id': str(response_data.get('id')),
                            'direction': response_data.get('direction', 'GOING'),
                            'passengers': json.dumps(response_data.get('passengers', [])),
                            'driver': str(response_data.get('driver')) if response_data.get('driver') is not None else None,
                            'vehicle': str(response_data.get('vehicle')) if response_data.get('vehicle') is not None else None,
                        }
                        # Handle datetime fields (only departure_datetime, as arrival_datetime is preserved)
                        departure_dt = response_data.get('departureDatetime')
                        if departure_dt:
                            try:
                                update_vals['departure_datetime'] = datetime.fromisoformat(departure_dt.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                update_vals['departure_datetime'] = None
                        # Update line_id if returned by API
                        line_external_id = response_data.get('line')
                        if line_external_id:
                            line = self.env['infrastructure.line'].search([('external_id', '=', line_external_id)], limit=1)
                            if line:
                                update_vals['line_id'] = line.id
                        # Preserve form inputs for status, location_type, lat, lng, arrival_datetime
                        api_status = response_data.get('status', 'IDLE').replace('FINISHED', 'COMPLETED') if response_data.get('status') in ['ON_GOING', 'FINISHED', 'CANCELLED', 'IDLE'] else 'IDLE'
                        api_location_type = response_data.get('locationType', 'UNKNOWN') if response_data.get('locationType') in ['LINE_STATION', 'INTER_STATION', 'UNKNOWN'] else 'UNKNOWN'
                        api_lat = response_data.get('lat', 0.0) or 0.0
                        api_lng = response_data.get('lng', 0.0) or 0.0
                        api_arrival_dt = response_data.get('arrivalDatetime')
                        # Log warnings if API response differs from payload
                        if api_status != api_data.get('status'):
                            _logger.warning("API returned status '%s' but payload sent '%s' for ride %s", api_status, api_data.get('status'), response_data.get('id'))
                        if api_location_type != (api_data.get('locationType') or 'UNKNOWN'):
                            _logger.warning("API returned locationType '%s' but payload sent '%s' for ride %s", api_location_type, api_data.get('locationType'), response_data.get('id'))
                        if api_lat != (api_data.get('lat') or 0.0):
                            _logger.warning("API returned lat '%s' but payload sent '%s' for ride %s", api_lat, api_data.get('lat'), response_data.get('id'))
                        if api_lng != (api_data.get('lng') or 0.0):
                            _logger.warning("API returned lng '%s' but payload sent '%s' for ride %s", api_lng, api_data.get('lng'), response_data.get('id'))
                        if api_arrival_dt != api_data.get('arrivalDatetime'):
                            _logger.warning("API returned arrivalDatetime '%s' but payload sent '%s' for ride %s", api_arrival_dt, api_data.get('arrivalDatetime'), response_data.get('id'))
                        # Apply updates
                        record.write(update_vals)
                        _logger.info("Updated ride with external_id %s from API response, preserving form inputs for status, location_type, lat, lng, arrival_datetime.", update_vals['external_id'])
                        return record
                    except json.JSONDecodeError:
                        raise UserError(f"API returned invalid JSON: {response.text} (Status: {response.status_code})")
                else:
                    raise UserError(f"Failed to create ride in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API POST request failed (attempt %s): %s", attempt + 1, str(e))
                if attempt == 0:
                    continue
                raise UserError(f"API request failed after retries: {str(e)}")

        return record

    @api.model
    def sync_rides_from_api(self):
        try:
            base_url = 'http://147.93.52.105:9080/ride'
            ride_id = 1
            synced_rides = 0
            consecutive_404s = 0

            while consecutive_404s < 3:
                try:
                    api_url = f'{base_url}/{ride_id}'
                    _logger.info("Fetching ride %s from %s", ride_id, api_url)
                    response = requests.get(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=5
                    )
                    _logger.info("API response for ride %s: Status %s", ride_id, response.status_code)

                    if response.status_code == 200:
                        ride = response.json()
                        ride_external_id = str(ride.get('id'))
                        # Skip if ride already exists in Odoo
                        if self.search([('external_id', '=', ride_external_id)], limit=1):
                            _logger.info("Ride with external_id %s already exists, skipping sync to preserve existing values.", ride_external_id)
                            ride_id += 1
                            consecutive_404s = 0
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
                            'vehicle': str(ride.get('vehicle')) if ride.get('driver') is not None else None,
                            'position_id': None
                        }

                        # Create with sync context to skip POST
                        self.with_context(from_sync=True).create(ride_data)
                        _logger.info("Synced new ride %s.", ride_external_id)
                        synced_rides += 1
                        consecutive_404s = 0
                        ride_id += 1

                    elif response.status_code == 404:
                        _logger.info("Ride %s not found.", ride_id)
                        consecutive_404s += 1
                        ride_id += 1
                    else:
                        _logger.warning("Failed to fetch ride %s: %s", ride_id, response.text)
                        ride_id += 1
                except requests.RequestException as e:
                    _logger.error("API request failed for ride %s: %s", ride_id, str(e))
                    ride_id += 1
                    continue

            _logger.info("Successfully synced %s new rides.", synced_rides)

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