import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class InfrastructureStation(models.Model):
    _name = 'infrastructure.station'
    _description = 'Infrastructure Station'

    name_ar = fields.Char(string='Name (Arabic)', required=True)
    name_en = fields.Char(string='Name (English)', required=True)
    name_fr = fields.Char(string='Name (French)', required=True)
    latitude = fields.Float(string='Latitude', default=0.0)
    longitude = fields.Float(string='Longitude', default=0.0)
    line_ids = fields.Many2many(
        'infrastructure.line',
        string='Lines',
        help='Select the lines associated with this station'
    )
    paths = fields.Text(string='Paths', default='[]')
    changes = fields.Text(string='Changes', default='{}')
    schedule = fields.Text(string='Schedule', default='[]')
    external_id = fields.Integer(string='External API ID', readonly=True)

    @api.constrains('paths', 'changes', 'schedule')
    def _check_json_fields(self):
        """Validate that paths, changes, and schedule are valid JSON."""
        for record in self:
            for field in ['paths', 'changes', 'schedule']:
                if record[field]:
                    try:
                        json.loads(record[field])
                    except json.JSONDecodeError:
                        raise ValidationError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

    def name_get(self):
        """Display name in dropdowns, prioritizing English name."""
        result = []
        for station in self:
            name = station.name_en or station.name_ar or station.name_fr or 'Unnamed Station'
            result.append((station.id, name))
        return result

    @api.model
    def create(self, vals):
        """Create a station in Odoo and sync with API."""
        # Validate JSON fields
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

        # Create the record in Odoo
        record = super(InfrastructureStation, self).create(vals)

        # Prepare API data
        api_data = {
            'nameAr': record.name_ar,
            'nameEn': record.name_en,
            'nameFr': record.name_fr,
            'lat': record.latitude or 0.0,
            'lng': record.longitude or 0.0,
            'paths': json.loads(record.paths) if record.paths else [],
            'lines': [line.external_id or line.id for line in record.line_ids],
            'changes': None,  # Set to null to match API GET response
            'schedule': json.loads(record.schedule) if record.schedule else []
        }

        # Send POST request to API
        try:
            api_url = 'http://147.93.52.105:8082/infra/station'
            payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
            _logger.info("Sending POST request to: %s with payload: %s", api_url, payload.decode('utf-8'))
            response = requests.post(
                api_url,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                data=payload
            )
            _logger.info("API POST %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 201:
                try:
                    response_data = response.text
                    if "Created Station with id:" in response_data:
                        external_id = int(response_data.split("Created Station with id: ")[1].strip())
                        record.write({'external_id': external_id})
                    else:
                        _logger.warning("No external_id found in API response: %s", response.text)
                except (ValueError, IndexError) as e:
                    _logger.error("Unable to parse external_id from API response: %s", str(e))
                    raise UserError(f"Failed to parse external_id: {str(e)}")
            else:
                raise UserError(f"Failed to create station in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        """Update a station in Odoo and sync with API."""
        # Validate JSON fields if provided
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

        # Update the record in Odoo
        result = super(InfrastructureStation, self).write(vals)

        # Sync updates to API for each record
        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for station %s: No external_id.", record.name_en or record.id)
                continue

            # Prepare API data
            api_data = {
                'nameAr': record.name_ar,
                'nameEn': record.name_en,
                'nameFr': record.name_fr,
                'lat': record.latitude or 0.0,
                'lng': record.longitude or 0.0,
                'paths': json.loads(record.paths) if record.paths else [],
                'lines': [line.external_id or line.id for line in record.line_ids],
                'changes': None,  # Set to null to match API GET response
                'schedule': json.loads(record.schedule) if record.schedule else []
            }

            # Send PUT request to API
            try:
                api_url = f'http://147.93.52.105:8082/infra/station/{record.external_id}'
                payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
                _logger.info("Sending PUT request to: %s with payload: %s", api_url, payload.decode('utf-8'))
                response = requests.put(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                # Accept 200, 201, or 204 as success
                if response.status_code not in (200, 201, 204):
                    raise UserError(f"Failed to update station in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        """Delete a station in Odoo and sync with API."""
        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:8082/infra/station/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'}
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    # Accept 200 or 204 as success
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete station %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.name_en or record.id, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for station %s: %s. Proceeding with Odoo deletion.", record.name_en or record.id, str(e))
            else:
                _logger.info("Skipping API delete for station %s: No external_id.", record.name_en or record.id)

        # Proceed with Odoo deletion
        return super(InfrastructureStation, self).unlink()

    @api.model
    def sync_stations_from_api(self):
        """Fetch stations from API and sync them into Odoo."""
        api_url = 'http://147.93.52.105:8082/infra/station'
        _logger.info("Sending GET request to: %s", api_url)

        try:
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'}
            )
            _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 200:
                stations = response.json()
                for station in stations:
                    try:
                        # Validate required fields
                        if not station.get('nameAr') or not station.get('nameEn') or not station.get('nameFr'):
                            _logger.warning("Skipping station with missing required name fields: %s", station)
                            continue

                        # Find lines by external_id
                        line_ids = []
                        for line_id in station.get('lines', []):
                            line = self.env['infrastructure.line'].search(
                                [('external_id', '=', line_id)], limit=1
                            )
                            if line:
                                line_ids.append(line.id)
                            else:
                                _logger.warning("Line with external_id %s not found for station %s", line_id, station.get('id'))

                        # Validate JSON fields
                        paths = json.dumps(station.get('paths', []))
                        changes = json.dumps(station.get('changes', {}) if station.get('changes') is not None else {})
                        schedule = json.dumps(station.get('schedule', []))
                        for field, value in [('paths', paths), ('changes', changes), ('schedule', schedule)]:
                            try:
                                json.loads(value)
                            except json.JSONDecodeError:
                                _logger.warning("Invalid %s format for station %s: %s. Using default.", field, station.get('id'), value)
                                if field == 'paths':
                                    paths = '[]'
                                elif field == 'changes':
                                    changes = '{}'
                                elif field == 'schedule':
                                    schedule = '[]'

                        # Prepare data
                        station_data = {
                            'name_ar': station.get('nameAr', ''),
                            'name_en': station.get('nameEn', ''),
                            'name_fr': station.get('nameFr', ''),
                            'latitude': station.get('lat', 0.0),
                            'longitude': station.get('lng', 0.0),
                            'paths': paths,
                            'changes': changes,
                            'schedule': schedule,
                            'line_ids': [(6, 0, line_ids)],
                            'external_id': station.get('id')
                        }

                        # Upsert in Odoo
                        existing_station = self.search([('external_id', '=', station.get('id'))], limit=1)
                        if existing_station:
                            existing_station.write(station_data)
                        else:
                            self.create(station_data)
                    except Exception as e:
                        _logger.error("Failed to sync station %s: %s", station.get('id', 'Unknown'), str(e))
                        continue
            else:
                raise UserError(f"Failed to fetch stations from API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API GET request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")