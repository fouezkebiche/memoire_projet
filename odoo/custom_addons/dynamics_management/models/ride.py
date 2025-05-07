import requests
import json
import logging
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class DynamicsRide(models.Model):
    _name = 'dynamics.ride'
    _description = 'Dynamics Ride'

    direction = fields.Selection(
        [('GOING', 'Going'), ('RETURNING', 'Returning')],
        string='Direction',
        required=True
    )
    departure_datetime = fields.Datetime(string='Departure Datetime')
    arrival_datetime = fields.Datetime(string='Arrival Datetime')
    status = fields.Selection(
        [('ON_GOING', 'On Going'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled'), ('IDLE', 'Idle')],
        string='Status',
        default='IDLE'
    )
    lat = fields.Float(string='Latitude', digits=(16, 8))
    lng = fields.Float(string='Longitude', digits=(16, 8))
    location_type = fields.Selection(
        [('LINE_STATION', 'Line Station'), ('INTER_STATION', 'Inter Station')],
        string='Location Type'
    )
    location_id = fields.Integer(string='Location ID')
    passengers = fields.Text(string='Passengers', default='[]')
    line_id = fields.Many2one('infrastructure.line', string='Line', required=True)
    driver_id = fields.Many2one('res.users', string='Driver')
    vehicle_id = fields.Many2one('dynamics.vehicle', string='Vehicle')
    external_id = fields.Integer(string='External API ID', readonly=True)
    position_id = fields.Many2one('dynamics.position', string='Position')

    @api.constrains('lat', 'lng')
    def _check_coordinates(self):
        for record in self:
            if record.lat and (record.lat < -90 or record.lat > 90):
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
            if record.lng and (record.lng < -180 or record.lng > 180):
                raise ValidationError("Longitude must be between -180 and 180 degrees.")

    @api.constrains('passengers')
    def _check_passengers(self):
        for record in self:
            if record.passengers:
                try:
                    json.loads(record.passengers)
                except json.JSONDecodeError:
                    raise ValidationError("Passengers must be valid JSON (e.g., [1, 2, 3]).")

    def _prepare_api_data(self):
        return {
            'id': self.external_id or None,
            'direction': self.direction,
            'departureDatetime': self.departure_datetime.isoformat() if self.departure_datetime else None,
            'arrivalDatetime': self.arrival_datetime.isoformat() if self.arrival_datetime else None,
            'status': self.status,
            'lat': self.lat or None,
            'lng': self.lng or None,
            'positionType': self.location_type or None,
            'passengers': json.loads(self.passengers) if self.passengers else [],
            'line': self.line_id.external_id or self.line_id.id,
            'driver': self.driver_id.id if self.driver_id else None,
            'locationId': self.location_id or None,
            'vehicle': self.vehicle_id.id if self.vehicle_id else None,
            'position': self.position_id.id if self.position_id else None
        }

    @api.model
    def create(self, vals):
        if vals.get('passengers'):
            try:
                json.loads(vals['passengers'])
            except json.JSONDecodeError:
                raise UserError("Passengers must be valid JSON (e.g., [1, 2, 3]).")

        record = super(DynamicsRide, self).create(vals)

        api_data = record._prepare_api_data()
        try:
            api_url = 'http://147.93.52.105:8080/ride'
            payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
            _logger.info("Sending POST request to: %s with payload: %s", api_url, payload.decode('utf-8'))
            response = requests.post(
                api_url,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                data=payload
            )
            _logger.info("API POST %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 201:
                response_data = response.json()
                record.write({'external_id': response_data.get('id')})
            else:
                raise UserError(f"Failed to create ride in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        if vals.get('passengers'):
            try:
                json.loads(vals['passengers'])
            except json.JSONDecodeError:
                raise UserError("Passengers must be valid JSON (e.g., [1, 2, 3]).")

        result = super(DynamicsRide, self).write(vals)

        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for ride %s: No external_id.", record.id)
                continue

            api_data = record._prepare_api_data()
            try:
                api_url = f'http://147.93.52.105:8080/ride/{record.external_id}'
                payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
                _logger.info("Sending PUT request to: %s with payload: %s", api_url, payload.decode('utf-8'))
                response = requests.put(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                if response.status_code not in (200, 201, 204):
                    raise UserError(f"Failed to update ride in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:8080/ride/{record.external_id}/cancel'
                    _logger.info("Sending PUT request to cancel ride: %s", api_url)
                    response = requests.put(
                        api_url,
                        headers={'Content-Type': 'application/json'}
                    )
                    _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code not in (200, 201, 204):
                        _logger.warning("Failed to cancel ride %s in API: %s (Status: %s). Proceeding with Odoo deletion.", 
                                        record.id, response.text, response.status_code)
                except requests.RequestException as e:
                    _logger.error("API PUT request failed for ride %s: %s. Proceeding with Odoo deletion.", record.id, str(e))

        return super(DynamicsRide, self).unlink()

    @api.model
    def sync_rides_from_api(self):
        try:
            base_url = 'http://147.93.52.105:8080/ride'
            max_id = 150  # Adjust based on expected number of rides
            rides = []
            synced_rides = 0

            # Fetch rides by ID
            for ride_id in range(1, max_id + 1):
                try:
                    api_url = f'{base_url}/{ride_id}'
                    _logger.info("Sending GET request to: %s", api_url)
                    response = requests.get(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=5
                    )
                    _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    
                    if response.status_code == 200:
                        rides.append(response.json())
                    elif response.status_code == 404:
                        _logger.info("Ride %s not found, skipping.", ride_id)
                        continue
                    else:
                        _logger.warning("Failed to fetch ride %s: %s (Status: %s)", ride_id, response.text, response.status_code)
                        continue
                except requests.RequestException as e:
                    _logger.error("API GET request failed for ride %s: %s", ride_id, str(e))
                    continue

            if not rides:
                _logger.warning("No rides fetched from API.")
                raise UserError("No rides could be fetched from the API.")

            _logger.info("Fetched %s rides from API.", len(rides))

            for ride in rides:
                try:
                    # Handle line_id
                    line_external_id = ride.get('line')
                    line = self.env['infrastructure.line'].search(
                        [('external_id', '=', line_external_id)], limit=1
                    )
                    if not line:
                        _logger.warning("Line with external_id %s not found for ride %s. Creating placeholder.", 
                                        line_external_id, ride.get('id'))
                        line = self.env['infrastructure.line'].create({
                            'name': f'Line {line_external_id} (Auto-created)',
                            'external_id': line_external_id
                        })

                    # Handle datetime format
                    departure_dt = ride.get('departureDatetime')
                    arrival_dt = ride.get('arrivalDatetime')
                    if departure_dt:
                        try:
                            departure_dt = datetime.fromisoformat(departure_dt.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            _logger.warning("Invalid departure datetime format for ride %s: %s", ride.get('id'), departure_dt)
                            departure_dt = None
                    if arrival_dt:
                        try:
                            arrival_dt = datetime.fromisoformat(arrival_dt.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            _logger.warning("Invalid arrival datetime format for ride %s: %s", ride.get('id'), departure_dt)
                            arrival_dt = None

                    # Handle status
                    status = ride.get('status')
                    if status == 'FINISHED':
                        status = 'COMPLETED'  # Map FINISHED to COMPLETED
                    if status not in ['ON_GOING', 'COMPLETED', 'CANCELLED', 'IDLE']:
                        _logger.warning("Invalid status for ride %s: %s. Setting to IDLE.", ride.get('id'), status)
                        status = 'IDLE'

                    # Handle vehicle
                    vehicle_id = ride.get('vehicle')
                    vehicle = self.env['dynamics.vehicle'].search(
                        [('id', '=', vehicle_id)], limit=1
                    ) if vehicle_id else None

                    # Handle position
                    position_id = ride.get('position')
                    position = self.env['dynamics.position'].search(
                        [('id', '=', position_id)], limit=1
                    ) if position_id else None

                    ride_data = {
                        'direction': ride.get('direction'),
                        'departure_datetime': departure_dt,
                        'arrival_datetime': arrival_dt,
                        'status': status,
                        'lat': ride.get('lat', 0.0),
                        'lng': ride.get('lng', 0.0),
                        'location_type': ride.get('locationType'),  # Changed from positionType to match API
                        'passengers': json.dumps(ride.get('passengers', [])),
                        'line_id': line.id,
                        'vehicle_id': vehicle.id if vehicle else None,
                        'external_id': ride.get('id'),
                        'location_id': ride.get('locationId'),
                        'position_id': position.id if position else None
                    }

                    existing_ride = self.search([('external_id', '=', ride.get('id'))], limit=1)
                    if existing_ride:
                        existing_ride.write(ride_data)
                        _logger.info("Updated ride %s in Odoo.", ride.get('id'))
                    else:
                        self.create(ride_data)
                        _logger.info("Created ride %s in Odoo.", ride.get('id'))
                    synced_rides += 1

                except Exception as e:
                    _logger.error("Failed to sync ride %s: %s", ride.get('id', 'Unknown'), str(e))
                    continue

            _logger.info("Successfully synced %s rides.", synced_rides)
            if synced_rides < len(rides):
                _logger.warning("Only %s out of %s rides were synced due to errors.", synced_rides, len(rides))

        except Exception as e:
            _logger.error("Sync rides failed: %s", str(e))
            raise UserError(f"Failed to sync rides: {str(e)}")

    @api.model
    def get_ongoing_rides(self):
        """Fetch ONGOING rides with valid lat/lng."""
        try:
            rides = self.search([
                ('status', '=', 'ON_GOING'),
                ('lat', '!=', False),
                ('lng', '!=', False)
            ])
            result = []
            for ride in rides:
                ride_data = {
                    'external_id': ride.external_id,
                    'direction': ride.direction,
                    'line_name': ride.line_id.display_name if ride.line_id else "Unknown",
                    'vehicle_plate': ride.vehicle_id.plate_number if ride.vehicle_id else "Unknown",
                    'lat': ride.lat,
                    'lng': ride.lng
                }
                result.append(ride_data)
            _logger.info("Fetched %s ONGOING rides with valid coordinates.", len(result))
            return result
        except Exception as e:
            _logger.error("Failed to fetch ONGOING rides: %s", str(e))
            raise UserError(f"Failed to fetch ONGOING rides: {str(e)}")