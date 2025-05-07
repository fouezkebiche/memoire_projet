import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class InfrastructureLineStation(models.Model):
    _name = 'infrastructure.line.station'
    _description = 'Infrastructure Line Station'

    order = fields.Integer(string='Order', required=True)
    stop_duration = fields.Integer(string='Stop Duration', default=0)
    direction = fields.Selection(
        [('GOING', 'Going'), ('RETURNING', 'Returning')],
        string='Direction',
        required=True
    )
    radius = fields.Integer(string='Radius', default=0)
    lat = fields.Float(string='Latitude', default=0.0)
    lng = fields.Float(string='Longitude', default=0.0)
    line_id = fields.Many2one(
        'infrastructure.line',
        string='Line',
        required=True
    )
    station_id = fields.Many2one(
        'infrastructure.station',
        string='Station',
        required=True
    )
    alertable = fields.Boolean(string='Alertable', default=False)
    efficient = fields.Boolean(string='Efficient', default=False)
    duration = fields.Integer(string='Duration', default=0)
    external_id = fields.Integer(string='External API ID', readonly=True)

    @api.constrains('lat', 'lng')
    def _check_coordinates(self):
        """Validate latitude and longitude."""
        for record in self:
            if record.lat and (record.lat < -90 or record.lat > 90):
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
            if record.lng and (record.lng < -180 or record.lng > 180):
                raise ValidationError("Longitude must be between -180 and 180 degrees.")

    def _prepare_station_data(self, station):
        """Prepare Station data for API payload."""
        return {
            'id': station.external_id or station.id,
            'nameAr': station.name_ar or 'Unknown',
            'nameEn': station.name_en or 'Unknown',
            'nameFr': station.name_fr or 'Unknown',
            'lat': station.latitude or 36.0,
            'lng': station.longitude or 6.0,
            'paths': json.loads(station.paths) if station.paths else [],
            'lines': [line.external_id or line.id for line in station.line_ids] or [station.external_id or station.id],
            'schedule': json.loads(station.schedule) if station.schedule else [],
            'changes': {}  # Required JsonObject
        }

    def _prepare_line_data(self, line):
        """Prepare LineData for API payload."""
        departure_station = line.departure_station_id
        terminus_station = line.terminus_station_id
        return {
            'id': line.external_id or line.id,
            'code': line.code or 'LINE',
            'color': line.color or '#000000',
            'departureStation': departure_station.name_en or str(departure_station.id) if departure_station else 'Unknown',
            'departureAddress': departure_station.name_en or 'Unknown' if departure_station else 'Unknown',
            'terminusStation': terminus_station.name_en or str(terminus_station.id) if terminus_station else 'Unknown',
            'terminusAddress': terminus_station.name_en or 'Unknown' if terminus_station else 'Unknown',
            'schedule': json.loads(line.schedule) if line.schedule else ['08:00']
        }

    @api.model
    def create(self, vals):
        """Create a line station in Odoo and sync with API."""
        record = super(InfrastructureLineStation, self).create(vals)
        station = self.env['infrastructure.station'].browse(record.station_id.id)
        line = self.env['infrastructure.line'].browse(record.line_id.id)

        # Validate line and station
        if not line.external_id:
            raise UserError(f"Line {line.id} has no external_id. Please sync lines first.")
        if not station.external_id:
            raise UserError(f"Station {station.id} has no external_id. Please sync stations first.")

        # Ensure station's lines include the current line
        station_data = self._prepare_station_data(station)
        if line.external_id not in station_data['lines']:
            station_data['lines'].append(line.external_id)

        api_data = {
            'order': record.order,
            'stopDuration': record.stop_duration,
            'direction': record.direction,  # GOING or RETURNING
            'radius': record.radius,
            'lat': record.lat or station.latitude or 36.0,
            'lng': record.lng or station.longitude or 6.0,
            'line': self._prepare_line_data(line),
            'station': station_data,
            'alertable': record.alertable,
            'efficient': record.efficient,
            'duration': record.duration
        }

        try:
            api_url = 'http://147.93.52.105:8082/infra/linestation'
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
                    if "Line Station created with id:" in response_data:
                        external_id = int(response_data.split("Line Station created with id: ")[1].strip())
                        record.write({'external_id': external_id})
                        _logger.info("Line station %s created with external_id %s", record.id, external_id)
                    else:
                        _logger.error("Expected 'Line Station created with id:' in API response, got: %s", response.text)
                        raise UserError(f"Failed to parse external_id from API response: {response.text}")
                except (ValueError, IndexError) as e:
                    _logger.error("Failed to parse external_id from API response '%s': %s", response.text, str(e))
                    raise UserError(f"Failed to parse external_id from API response: {str(e)}")
            else:
                raise UserError(f"Failed to create line station in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        """Update a line station in Odoo and sync with API."""
        result = super(InfrastructureLineStation, self).write(vals)
        for record in self:
            station = self.env['infrastructure.station'].browse(record.station_id.id)
            line = self.env['infrastructure.line'].browse(record.line_id.id)

            # Validate line and station
            if not line.external_id:
                raise UserError(f"Line {line.id} has no external_id. Please sync lines first.")
            if not station.external_id:
                raise UserError(f"Station {station.id} has no external_id. Please sync stations first.")

            # Ensure station's lines include the current line
            station_data = self._prepare_station_data(station)
            if line.external_id not in station_data['lines']:
                station_data['lines'].append(line.external_id)

            api_data = {
                'order': record.order,
                'stopDuration': record.stop_duration,
                'direction': record.direction,  # GOING or RETURNING
                'radius': record.radius,
                'lat': record.lat or station.latitude or 36.0,
                'lng': record.lng or station.longitude or 6.0,
                'line': self._prepare_line_data(line),
                'station': station_data,
                'alertable': record.alertable,
                'efficient': record.efficient,
                'duration': record.duration
            }

            # If no external_id, attempt to create in API first
            if not record.external_id:
                _logger.warning("Line station %s has no external_id. Attempting to create in API.", record.id)
                try:
                    api_url = 'http://147.93.52.105:8082/infra/linestation'
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
                            if "Line Station created with id:" in response_data:
                                external_id = int(response_data.split("Line Station created with id: ")[1].strip())
                                record.write({'external_id': external_id})
                                _logger.info("Line station %s created in API with external_id %s", record.id, external_id)
                            else:
                                _logger.error("Expected 'Line Station created with id:' in API response, got: %s", response.text)
                                raise UserError(f"Failed to parse external_id from API response: {response.text}")
                        except (ValueError, IndexError) as e:
                            _logger.error("Failed to parse external_id from API POST response '%s': %s", response.text, str(e))
                            raise UserError(f"Failed to parse external_id: {str(e)}")
                    else:
                        _logger.error("Failed to create line station in API: %s (Status: %s)", response.text, response.status_code)
                        raise UserError(f"Failed to create line station in API: {response.text} (Status: {response.status_code})")
                except requests.RequestException as e:
                    _logger.error("API POST request failed for line station %s: %s", record.id, str(e))
                    raise UserError(f"API POST request failed: {str(e)}")

            # Proceed with update
            try:
                api_url = f'http://147.93.52.105:8082/infra/linestation/{record.external_id}'
                payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
                _logger.info("Sending PUT request to: %s with payload: %s", api_url, payload.decode('utf-8'))
                response = requests.put(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                if response.status_code == 201:
                    _logger.info("Line station %s updated successfully in API", record.external_id)
                elif response.status_code in (200, 204):
                    _logger.info("Line station %s updated with status %s", record.external_id, response.status_code)
                else:
                    raise UserError(f"Failed to update line station in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed for line station %s: %s", record.id, str(e))
                raise UserError(f"API PUT request failed: {str(e)}")

        return result

    def unlink(self):
        """Delete a line station in Odoo and sync with API."""
        for record in self:
            if record.external_id:
                try:
                    # Verify the record exists in the API
                    api_url = f'http://147.93.52.105:8082/infra/linestation/{record.external_id}'
                    _logger.info("Sending GET request to verify: %s", api_url)
                    get_response = requests.get(
                        api_url,
                        headers={'Content-Type': 'application/json'}
                    )
                    _logger.info("API GET %s response: %s (Status: %s)", api_url, get_response.text, get_response.status_code)
                    if get_response.status_code == 200:
                        # Record exists, attempt DELETE with retry
                        for attempt in range(2):  # Try twice (initial + one retry)
                            _logger.info("Sending DELETE request to: %s (Attempt %s)", api_url, attempt + 1)
                            delete_response = requests.delete(
                                api_url,
                                headers={'Content-Type': 'application/json'}
                            )
                            _logger.info("API DELETE %s response: %s (Status: %s, Headers: %s)", 
                                        api_url, delete_response.text, delete_response.status_code, dict(delete_response.headers))
                            if delete_response.status_code in (200, 204):
                                if "Line Station deleted with id:" in delete_response.text:
                                    deleted_id = delete_response.text.split("Line Station deleted with id: ")[1].strip()
                                    _logger.info("Line station %s deleted successfully in API with id %s", record.id, deleted_id)
                                else:
                                    _logger.warning("Expected 'Line Station deleted with id:' in API response, got: %s", delete_response.text)
                                break  # Success, exit retry loop
                            elif delete_response.status_code == 404:
                                if attempt == 0:
                                    _logger.warning("DELETE failed with 404 for line station %s (external_id: %s). Retrying...", 
                                                   record.id, record.external_id)
                                    continue
                                _logger.warning("Line station %s (external_id: %s) not found in API after GET confirmed existence. Proceeding with Odoo deletion.", 
                                               record.id, record.external_id)
                                break  # Proceed after final attempt
                            else:
                                _logger.error("Failed to delete line station %s in API: %s (Status: %s)", 
                                             record.id, delete_response.text, delete_response.status_code)
                                raise UserError(f"Failed to delete line station in API: {delete_response.text} (Status: {delete_response.status_code})")
                    elif get_response.status_code == 404:
                        _logger.info("Line station %s not found in API (external_id: %s). Proceeding with Odoo deletion.", 
                                    record.id, record.external_id)
                    else:
                        _logger.error("Failed to verify line station %s in API: %s (Status: %s)", 
                                     record.id, get_response.text, get_response.status_code)
                        raise UserError(f"Failed to verify line station in API: {get_response.text} (Status: {get_response.status_code})")
                except requests.RequestException as e:
                    _logger.error("API request failed for line station %s: %s", record.id, str(e))
                    raise UserError(f"API request failed: {str(e)}")
            else:
                _logger.info("Skipping API delete for line station %s: No external_id.", record.id)

        return super(InfrastructureLineStation, self).unlink()

    @api.model
    def clean_duplicate_line_stations(self):
        """Remove duplicate line stations based on external_id, keeping the latest record."""
        _logger.info("Starting deduplication of line stations")
        records = self.search([('external_id', '!=', False)], order='external_id, id desc')
        if not records:
            _logger.info("No line stations with external_id found for deduplication")
            return

        external_id_groups = {}
        for record in records:
            if record.external_id not in external_id_groups:
                external_id_groups[record.external_id] = []
            external_id_groups[record.external_id].append(record)

        for external_id, group in external_id_groups.items():
            if len(group) > 1:
                keep_record = group[0]
                delete_records = group[1:]
                _logger.info("Found %s duplicates for external_id %s. Keeping record id %s, deleting %s", 
                             len(delete_records), external_id, keep_record.id, [r.id for r in delete_records])
                for record in delete_records:
                    try:
                        record.unlink()
                    except Exception as e:
                        _logger.error("Failed to delete duplicate line station id %s: %s", record.id, str(e))

        no_external_id = self.search([('external_id', '=', False)])
        if no_external_id:
            _logger.warning("Found %s line stations without external_id: %s", 
                            len(no_external_id), [r.id for r in no_external_id])

    @api.model
    def sync_linestations_from_api(self):
        """Fetch all line stations (GOING and RETURNING) from API and sync into Odoo without duplicates."""
        self.clean_duplicate_line_stations()

        try:
            self.env['infrastructure.station'].sync_stations_from_api()
            self.env['infrastructure.line'].sync_lines_from_api()
        except Exception as e:
            _logger.error("Failed to sync stations or lines: %s", str(e))
            raise UserError(f"Failed to sync stations or lines: {str(e)}")

        lines = self.env['infrastructure.line'].search([])
        if not lines:
            _logger.warning("No lines found in Odoo. Cannot fetch line stations.")
            raise UserError("No lines found in Odoo. Please sync lines first.")

        base_api_url = 'http://147.93.52.105:8082/infra/linestation'
        directions = ['GOING', 'RETURNING']

        for line in lines:
            for direction in directions:
                api_url = f"{base_api_url}?lineId={line.external_id}&direction={direction}"
                _logger.info("Sending GET request to: %s", api_url)

                try:
                    response = requests.get(
                        api_url,
                        headers={'Content-Type': 'application/json'}
                    )
                    _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code == 200:
                        line_stations = response.json()
                        for ls in line_stations:
                            try:
                                if not ls.get('line') or not ls.get('station'):
                                    _logger.warning("Skipping line station with missing line or station: %s", ls.get('id', 'Unknown'))
                                    continue

                                line_record = self.env['infrastructure.line'].search(
                                    [('external_id', '=', ls['line'].get('id'))], limit=1
                                )
                                if not line_record:
                                    _logger.warning("Line with external_id %s not found for line station %s", ls['line'].get('id'), ls.get('id', 'Unknown'))
                                    continue

                                station = self.env['infrastructure.station'].search(
                                    [('external_id', '=', ls['station'].get('id'))], limit=1
                                )
                                if not station:
                                    _logger.warning("Station with external_id %s not found for line station %s", ls['station'].get('id'), ls.get('id', 'Unknown'))
                                    continue

                                ls_direction = ls.get('direction')

                                ls_data = {
                                    'order': ls.get('order', 0),
                                    'stop_duration': ls.get('stopDuration', 0),
                                    'direction': ls_direction,
                                    'radius': ls.get('radius', 0),
                                    'lat': ls.get('lat', 0.0),
                                    'lng': ls.get('lng', 0.0),
                                    'line_id': line_record.id,
                                    'station_id': station.id,
                                    'alertable': ls.get('alertable', False),
                                    'efficient': ls.get('efficient', False),
                                    'duration': ls.get('duration', 0),
                                    'external_id': ls.get('id')
                                }

                                existing_ls = self.search([('external_id', '=', ls.get('id'))], limit=1)
                                if existing_ls:
                                    _logger.info("Updating existing line station with external_id %s", ls.get('id'))
                                    existing_ls.write(ls_data)
                                else:
                                    _logger.info("Creating new line station with external_id %s", ls.get('id'))
                                    self.create(ls_data)
                            except Exception as e:
                                _logger.error("Failed to sync line station %s: %s", ls.get('id', 'Unknown'), str(e))
                                continue
                    else:
                        _logger.warning("Failed to fetch line stations for line %s, direction %s: %s (Status: %s)", 
                                        line.external_id, direction, response.text, response.status_code)
                        continue
                except requests.RequestException as e:
                    _logger.error("API GET request failed for %s: %s", api_url, str(e))
                    continue