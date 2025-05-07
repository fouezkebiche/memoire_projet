import requests
import json
import logging
import re
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class InfrastructureLine(models.Model):
    _name = 'infrastructure.line'
    _description = 'Infrastructure Line'

    code = fields.Char(string='Code', required=True)
    color = fields.Char(string='Color', required=True)
    line_type_id = fields.Many2one(
        'infrastructure.line.type',
        string='Line Type',
        required=True
    )
    enterprise_code = fields.Char(string='Enterprise Code', required=True)
    departure_station_id = fields.Many2one(
        'infrastructure.station',
        string='Departure Station',
        required=True
    )
    terminus_station_id = fields.Many2one(
        'infrastructure.station',
        string='Terminus Station',
        required=True
    )
    schedule = fields.Text(string='Schedule')
    external_id = fields.Integer(string='External API ID', readonly=True)

    # Map color indices to hex codes
    COLOR_INDEX_TO_HEX = {
        '1': '#FF0000',  # Red
        '2': '#00FF00',  # Green
        '3': '#0000FF',  # Blue
        '4': '#FFFF00',  # Yellow
        '5': '#FF00FF',  # Magenta
        '6': '#00FFFF',  # Cyan
        '7': '#800080',  # Purple
        '8': '#FFA500',  # Orange
        '9': '#A52A2A',  # Brown
        '10': '#FFFFFF', # White
    }

    @api.constrains('color')
    def _check_color(self):
        """Validate or convert color to a valid hex code."""
        for record in self:
            if not record.color:
                continue
            # Check if color is a valid hex code
            if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', record.color):
                continue
            # Check if color is an index and convert to hex
            if record.color in self.COLOR_INDEX_TO_HEX:
                record.color = self.COLOR_INDEX_TO_HEX[record.color]
            else:
                raise ValidationError(
                    "Color must be a valid hex code (e.g., #FF0000) or a valid color index (1-10)."
                )

    def _prepare_station_data(self, station):
        """Prepare Station data for API payload."""
        return {
            'id': station.external_id or station.id,
            'nameAr': station.name_ar or '',
            'nameEn': station.name_en or '',
            'nameFr': station.name_fr or '',
            'lat': station.latitude or 0.0,
            'lng': station.longitude or 0.0,
            'paths': json.loads(station.paths) if station.paths else [],
            'lines': [line.external_id or line.id for line in station.line_ids],
            'schedule': json.loads(station.schedule) if station.schedule else []
        }

    @api.model
    def create(self, vals):
        # Validate schedule if provided
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., '[\"08:00\", \"09:00\"]').")

        # Convert color index to hex if necessary
        if vals.get('color') in self.COLOR_INDEX_TO_HEX:
            vals['color'] = self.COLOR_INDEX_TO_HEX[vals['color']]

        # Create the record in Odoo
        record = super(InfrastructureLine, self).create(vals)

        # Prepare Station data
        departure_station = self.env['infrastructure.station'].browse(record.departure_station_id.id)
        terminus_station = self.env['infrastructure.station'].browse(record.terminus_station_id.id)

        # Prepare data for API
        api_data = {
            'code': record.code,
            'color': record.color,
            'lineType': record.line_type_id.id,
            'enterpriseCode': record.enterprise_code,
            'departureStation': self._prepare_station_data(departure_station),
            'terminusStation': self._prepare_station_data(terminus_station),
            'lineStations': [
                {
                    'order': 1,
                    'stopDuration': 0,
                    'direction': 'GOING',
                    'station': self._prepare_station_data(departure_station),
                    'radius': 0,
                    'lat': departure_station.latitude or 0.0,
                    'lng': departure_station.longitude or 0.0,
                    'alertable': False,
                    'efficient': True,
                    'duration': 0
                },
                {
                    'order': 2,
                    'stopDuration': 0,
                    'direction': 'GOING',
                    'station': self._prepare_station_data(terminus_station),
                    'radius': 0,
                    'lat': terminus_station.latitude or 0.0,
                    'lng': terminus_station.longitude or 0.0,
                    'alertable': False,
                    'efficient': True,
                    'duration': 0
                }
            ],
            'schedule': json.loads(record.schedule) if record.schedule else []
        }

        # Send POST request to API
        try:
            api_url = 'http://147.93.52.105:8082/infra/line'
            _logger.info("Sending POST request to: %s with payload: %s", api_url, json.dumps(api_data))
            response = requests.post(
                api_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(api_data)
            )
            _logger.info("API POST %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 201:
                # Try to extract ID from response if API returns it
                try:
                    response_data = response.text  # API returns string like "Line created with id: 9"
                    if "Line created with id:" in response_data:
                        external_id = int(response_data.split("Line created with id: ")[1])
                        record.write({'external_id': external_id})
                except (ValueError, IndexError):
                    pass  # Unable to parse ID
            else:
                raise UserError(f"Failed to create line in API: {response.text}")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        """Override write to sync updates with the API."""
        # Convert color index to hex if necessary
        if vals.get('color') in self.COLOR_INDEX_TO_HEX:
            vals['color'] = self.COLOR_INDEX_TO_HEX[vals['color']]

        # Validate schedule if provided
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., '[\"08:00\", \"09:00\"]').")

        # Update the record in Odoo
        result = super(InfrastructureLine, self).write(vals)

        # Sync updates to API for each record
        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for line %s: No external_id.", record.code)
                continue

            # Prepare Station data
            departure_station = self.env['infrastructure.station'].browse(
                record.departure_station_id.id
            )
            terminus_station = self.env['infrastructure.station'].browse(
                record.terminus_station_id.id
            )

            # Prepare data for API
            api_data = {
                'code': record.code,
                'color': record.color,
                'lineType': record.line_type_id.id,
                'enterpriseCode': record.enterprise_code,
                'departureStation': self._prepare_station_data(departure_station),
                'terminusStation': self._prepare_station_data(terminus_station),
                'lineStations': [
                    {
                        'order': 1,
                        'stopDuration': 0,
                        'direction': 'GOING',
                        'station': self._prepare_station_data(departure_station),
                        'radius': 0,
                        'lat': departure_station.latitude or 0.0,
                        'lng': departure_station.longitude or 0.0,
                        'alertable': False,
                        'efficient': True,
                        'duration': 0
                    },
                    {
                        'order': 2,
                        'stopDuration': 0,
                        'direction': 'GOING',
                        'station': self._prepare_station_data(terminus_station),
                        'radius': 0,
                        'lat': terminus_station.latitude or 0.0,
                        'lng': terminus_station.longitude or 0.0,
                        'alertable': False,
                        'efficient': True,
                        'duration': 0
                    }
                ],
                'schedule': json.loads(record.schedule) if record.schedule else []
            }

            # Send PUT request to API
            try:
                api_url = f'http://147.93.52.105:8082/infra/line/{record.external_id}'
                _logger.info("Sending PUT request to: %s with payload: %s", api_url, json.dumps(api_data))
                response = requests.put(
                    api_url,
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps(api_data)
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                # Accept 200, 201, or 204 as success
                if response.status_code not in (200, 201, 204):
                    raise UserError(f"Failed to update line in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        """Override unlink to sync deletion with the API."""
        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:8082/infra/line/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'}
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    # Accept 200 or 204 as success
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete line %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.code, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for line %s: %s. Proceeding with Odoo deletion.", record.code, str(e))
            else:
                _logger.info("Skipping API delete for line %s: No external_id.", record.code)

        # Proceed with Odoo deletion
        return super(InfrastructureLine, self).unlink()

    @api.model
    def sync_lines_from_api(self):
        """Fetch lines from API and sync them into Odoo."""
        # Sync stations first to ensure all stations are available
        try:
            self.env['infrastructure.station'].sync_stations_from_api()
        except Exception as e:
            _logger.error("Failed to sync stations: %s", str(e))
            raise UserError(f"Failed to sync stations: {str(e)}")

        try:
            api_url = 'http://147.93.52.105:8082/infra/line'
            _logger.info("Sending GET request to: %s", api_url)
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'}
            )
            _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 200:
                lines = response.json()
                for line in lines:
                    try:
                        # Validate required fields
                        if not line.get('code') or not line.get('enterpriseCode'):
                            _logger.warning("Skipping line with missing code or enterpriseCode: %s", line)
                            continue

                        # Find or create line_type
                        line_type_id = line.get('lineType')
                        if not line_type_id:
                            _logger.warning("Skipping line with missing lineType: %s", line.get('code', 'Unknown'))
                            continue
                        line_type = self.env['infrastructure.line.type'].search(
                            [('id', '=', line_type_id)], limit=1
                        )
                        if not line_type:
                            line_type = self.env['infrastructure.line.type'].create({
                                'name': f"Type {line_type_id}",
                                'code': str(line_type_id)
                            })

                        # Find stations by external_id
                        departure_station_id = line.get('departureStation', {}).get('id')
                        if not departure_station_id:
                            _logger.warning("Skipping line with missing departureStation: %s", line.get('code'))
                            continue
                        departure_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', departure_station_id)], limit=1
                        )
                        if not departure_station:
                            departure_station = self.env['infrastructure.station'].create({
                                'name_ar': line['departureStation'].get('nameAr', 'Unknown'),
                                'name_en': line['departureStation'].get('nameEn', 'Unknown'),
                                'name_fr': line['departureStation'].get('nameFr', 'Unknown'),
                                'latitude': line['departureStation'].get('lat', 0.0),
                                'longitude': line['departureStation'].get('lng', 0.0),
                                'external_id': departure_station_id,
                                'paths': json.dumps(line['departureStation'].get('paths', [])),
                                'schedule': json.dumps(line['departureStation'].get('schedule', [])),
                            })

                        terminus_station_id = line.get('terminusStation', {}).get('id')
                        if not terminus_station_id:
                            _logger.warning("Skipping line with missing terminusStation: %s", line.get('code'))
                            continue
                        terminus_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', terminus_station_id)], limit=1
                        )
                        if not terminus_station:
                            terminus_station = self.env['infrastructure.station'].create({
                                'name_ar': line['terminusStation'].get('nameAr', 'Unknown'),
                                'name_en': line['terminusStation'].get('nameEn', 'Unknown'),
                                'name_fr': line['terminusStation'].get('nameFr', 'Unknown'),
                                'latitude': line['terminusStation'].get('lat', 0.0),
                                'longitude': line['terminusStation'].get('lng', 0.0),
                                'external_id': terminus_station_id,
                                'paths': json.dumps(line['terminusStation'].get('paths', [])),
                                'schedule': json.dumps(line['terminusStation'].get('schedule', [])),
                            })

                        # Handle color: use hex or convert to hex
                        color = line.get('color', '#000000')
                        # If color is a number (index), convert to hex
                        if color in self.COLOR_INDEX_TO_HEX:
                            color = self.COLOR_INDEX_TO_HEX[color]
                        # If not a valid hex, log and use default
                        elif not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
                            _logger.warning("Invalid color format for line %s: %s. Using default #000000.", line.get('code'), color)
                            color = '#000000'

                        # Prepare schedule
                        schedule = json.dumps(line.get('schedule', []))
                        try:
                            json.loads(schedule)
                        except json.JSONDecodeError:
                            _logger.warning("Invalid schedule format for line %s: %s. Using empty schedule.", line.get('code'), schedule)
                            schedule = '[]'

                        # Upsert line in Odoo
                        existing_line = self.search([('external_id', '=', line.get('id'))], limit=1)
                        line_data = {
                            'code': line.get('code'),
                            'color': color,
                            'line_type_id': line_type.id,
                            'enterprise_code': line.get('enterpriseCode'),
                            'departure_station_id': departure_station.id,
                            'terminus_station_id': terminus_station.id,
                            'schedule': schedule,
                            'external_id': line.get('id'),
                        }
                        if existing_line:
                            existing_line.write(line_data)
                        else:
                            self.create(line_data)
                    except Exception as e:
                        _logger.error("Failed to sync line %s: %s", line.get('code', 'Unknown'), str(e))
                        continue
            else:
                raise UserError(f"Failed to fetch lines from API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API GET request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")