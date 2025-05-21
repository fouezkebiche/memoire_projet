import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

class InfrastructureStation(models.Model):
    _name = 'infrastructure.station'
    _description = 'Infrastructure Station'
    _rec_name = 'name_en'

    name_ar = fields.Char(string='Name (Arabic)', required=True)
    name_en = fields.Char(string='Name (English)', required=True)
    name_fr = fields.Char(string='Name (French)', required=True)
    latitude = fields.Float(string='Latitude', default=36.7538)  # Default to Algiers
    longitude = fields.Float(string='Longitude', default=3.0588)
    line_ids = fields.Many2many(
        'infrastructure.line',
        string='Lines',
        help='Select the lines associated with this station'
    )
    paths = fields.Text(string='Paths', default='[]')
    changes = fields.Text(string='Changes', default='{}')
    schedule = fields.Text(string='Schedule', default='[]')
    external_id = fields.Integer(string='External API ID', readonly=True, index=True)
    location_picker = fields.Boolean(string='Location Picker', default=True)

    @api.constrains('paths', 'changes', 'schedule')
    def _check_json_fields(self):
        for record in self:
            for field in ['paths', 'changes', 'schedule']:
                if record[field]:
                    try:
                        json.loads(record[field])
                    except json.JSONDecodeError:
                        raise ValidationError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

    def name_get(self):
        result = []
        for station in self:
            name = station.name_en or station.name_ar or station.name_fr or f'Station {station.id}'
            _logger.debug("name_get for station ID %s: %s", station.id, name)
            result.append((station.id, name))
        return result

    @api.model
    def create(self, vals):
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

        # During sync, skip API POST and just create the record in Odoo
        if self._context.get('from_sync'):
            _logger.info("Creating station in Odoo from sync: %s (external_id: %s)", vals.get('name_en'), vals.get('external_id'))
            return super(InfrastructureStation, self).create(vals)

        record = super(InfrastructureStation, self).create(vals)

        api_data = {
            'nameAr': record.name_ar,
            'nameEn': record.name_en,
            'nameFr': record.name_fr,
            'lat': record.latitude or 0.0,
            'lng': record.longitude or 0.0,
            'paths': json.loads(record.paths) if record.paths else [],
            'lines': [line.external_id or line.id for line in record.line_ids],
            'changes': json.loads(record.changes) if record.changes else {},
            'schedule': json.loads(record.schedule) if record.schedule else []
        }

        try:
            api_url = 'http://147.93.52.105:9000/infra/station'
            payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
            _logger.info("Sending POST request to: %s with payload: %s", api_url, payload.decode('utf-8'))
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
                    external_id = response_data.get('id')
                    if not external_id:
                        raise ValueError("No external_id found in JSON response")
                except json.JSONDecodeError:
                    response_text = response.text.strip()
                    if "Created Station with id:" in response_text:
                        try:
                            external_id = int(response_text.split("Created Station with id:")[1].strip())
                        except (IndexError, ValueError):
                            _logger.error("Unable to parse external_id from text response: %s", response_text)
                            raise UserError(f"Failed to parse external_id from API response: {response_text}")
                    else:
                        _logger.error("Unexpected response format: %s", response_text)
                        raise UserError(f"Unexpected API response format: {response_text}")
                
                self._cr.execute('UPDATE infrastructure_station SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to station %s", external_id, record.name_en)
            else:
                raise UserError(f"Failed to create station in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(f"{field.capitalize()} must be valid JSON (e.g., [], {{}}, or [\"08:00\"]).")

        # Skip API update during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API update for station during sync: %s", self.name_en)
            return super(InfrastructureStation, self).write(vals)

        result = super(InfrastructureStation, self).write(vals)

        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for station %s: No external_id.", record.name_en or record.id)
                continue

            api_data = {
                'nameAr': record.name_ar,
                'nameEn': record.name_en,
                'nameFr': record.name_fr,
                'lat': record.latitude or 0.0,
                'lng': record.longitude or 0.0,
                'paths': json.loads(record.paths) if record.paths else [],
                'lines': [line.external_id or line.id for line in record.line_ids],
                'changes': json.loads(record.changes) if record.changes else {},
                'schedule': json.loads(record.schedule) if record.schedule else []
            }

            try:
                api_url = f'http://147.93.52.105:9000/infra/station/{record.external_id}'
                payload = json.dumps(api_data, ensure_ascii=False).encode('utf-8')
                _logger.info("Sending PUT request to: %s with payload: %s", api_url, payload.decode('utf-8'))
                response = requests.put(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload,
                    timeout=10
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                if response.status_code not in (200, 201, 204):
                    raise UserError(f"Failed to update station in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        # Skip API delete during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for station during sync: %s", self.name_en)
            return super(InfrastructureStation, self).unlink()

        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:9000/infra/station/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete station %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.name_en or record.id, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for station %s: %s.", record.name_en or record.id, str(e))
            else:
                _logger.info("Skipping API delete for station %s: No external_id.", record.name_en or record.id)

        return super(InfrastructureStation, self).unlink()

    @api.model
    def sync_infrastructure(self, sync_stations=False, sync_lines=False, sync_line_stations=False):
        """
        Synchronize infrastructure data from API based on selected options.
        Fetches data from API, compares with Odoo DB, creates new records if needed,
        and updates existing ones without modifying the API.
        :param sync_stations: Boolean to sync stations
        :param sync_lines: Boolean to sync lines
        :param sync_line_stations: Boolean to sync line stations
        :return: dict with sync results
        """
        result = {
            'stations': {'synced': 0, 'skipped': 0},
            'lines': {'synced': 0, 'skipped': 0},
            'line_stations': {'synced': 0, 'skipped': 0},
            'messages': []
        }

        if not any([sync_stations, sync_lines, sync_line_stations]):
            raise UserError("Please select at least one entity to sync (Stations, Lines, or Line Stations)")

        try:
            # Sync stations if requested
            if sync_stations:
                api_url = 'http://147.93.52.105:9000/infra/station'
                _logger.info("Fetching all stations from API: %s", api_url)
                response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=30)
                if response.status_code != 200:
                    raise UserError(f"Failed to fetch stations from API: {response.text} (Status: {response.status_code})")

                stations = response.json()
                _logger.info("API returned %s stations", len(stations))

                synced_count = 0
                skipped_count = 0
                existing_stations = self.search([('external_id', '!=', False)])
                existing_station_map = {station.external_id: station for station in existing_stations}

                for station in stations:
                    external_id = station.get('id')
                    if not external_id:
                        _logger.warning("Skipping station with missing id: %s", station)
                        skipped_count += 1
                        continue

                    name_ar = station.get('nameAr', '')
                    name_en = station.get('nameEn', '')
                    name_fr = station.get('nameFr', '')
                    if any(name.lower().startswith('test') for name in [name_ar, name_en, name_fr]) or not all([name_ar, name_en, name_fr]):
                        _logger.info(f"Skipping test or incomplete station with external_id {external_id}")
                        skipped_count += 1
                        continue

                    line_ids = []
                    for line_id in station.get('lines', []):
                        line = self.env['infrastructure.line'].search([('external_id', '=', line_id)], limit=1)
                        if line:
                            line_ids.append(line.id)

                    station_data = {
                        'name_ar': name_ar,
                        'name_en': name_en,
                        'name_fr': name_fr,
                        'latitude': float(station.get('lat', 36.7538)),
                        'longitude': float(station.get('lng', 3.0588)),
                        'paths': json.dumps(station.get('paths', [])),
                        'changes': json.dumps(station.get('changes', {}) or {}),
                        'schedule': json.dumps(station.get('schedule', [])),
                        'line_ids': [(6, 0, line_ids)],
                        'external_id': external_id,
                        'location_picker': True
                    }

                    api_data_serialized = self._serialize_station_data(station, line_ids)
                    existing_station = existing_station_map.get(external_id)

                    if existing_station:
                        existing_data_serialized = self._serialize_existing_station(existing_station)
                        if existing_data_serialized == api_data_serialized:
                            _logger.debug(f"Skipping station with external_id {external_id}: No changes")
                            skipped_count += 1
                            continue
                        existing_station.with_context(from_sync=True).write(station_data)
                        _logger.info(f"Updated station with external_id {external_id}")
                        synced_count += 1
                    else:
                        self.with_context(from_sync=True).create(station_data)
                        _logger.info(f"Created station with external_id {external_id}")
                        synced_count += 1

                result['stations'] = {'synced': synced_count, 'skipped': skipped_count}
                result['messages'].append(f"Stations sync completed: {synced_count} synced, {skipped_count} skipped")

                # Update last sync timestamp
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.station.last_sync', current_time)

            # Sync lines if requested
            if sync_lines:
                api_url = 'http://147.93.52.105:9000/infra/line'
                _logger.info("Fetching all lines from API: %s", api_url)
                response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=30)
                if response.status_code != 200:
                    raise UserError(f"Failed to fetch lines from API: {response.text} (Status: {response.status_code})")

                lines = response.json()
                _logger.info("API returned %s lines", len(lines))

                synced_count = 0
                skipped_count = 0
                existing_lines = self.env['infrastructure.line'].search([('external_id', '!=', False)])
                existing_line_map = {line.external_id: line for line in existing_lines}

                for line in lines:
                    external_id = line.get('id')
                    if not external_id:
                        _logger.warning("Skipping line with missing id: %s", line)
                        skipped_count += 1
                        continue

                    code = line.get('code', '')
                    enterprise_code = line.get('enterpriseCode', '')
                    if not code or not enterprise_code or enterprise_code.lower() == 'test':
                        _logger.info(f"Skipping test or incomplete line with external_id {external_id}")
                        skipped_count += 1
                        continue

                    departure_station = None
                    if line.get('departureStation', {}).get('id'):
                        departure_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', line['departureStation']['id'])], limit=1
                        )
                    terminus_station = None
                    if line.get('terminusStation', {}).get('id'):
                        terminus_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', line['terminusStation']['id'])], limit=1
                        )

                    line_data = {
                        'code': code,
                        'color': line.get('color', '#000000'),
                        'line_type': str(line.get('lineType', '1')),
                        'enterprise_code': enterprise_code,
                        'departure_station_id': departure_station.id if departure_station else False,
                        'terminus_station_id': terminus_station.id if terminus_station else False,
                        'schedule': json.dumps(line.get('schedule', [])),
                        'external_id': external_id
                    }

                    # Note: We do not handle line_station_ids here to avoid deleting them
                    api_data_serialized = self.env['infrastructure.line']._serialize_line_data(
                        line,
                        departure_station.id if departure_station else False,
                        terminus_station.id if terminus_station else False,
                        []  # Avoid including line stations in comparison to prevent deletion
                    )

                    existing_line = existing_line_map.get(external_id)
                    if existing_line:
                        existing_data_serialized = self.env['infrastructure.line']._serialize_existing_line(existing_line)
                        if existing_data_serialized == api_data_serialized:
                            _logger.debug(f"Skipping line with external_id {external_id}: No changes")
                            skipped_count += 1
                            continue
                        existing_line.with_context(from_sync=True).write(line_data)
                        _logger.info(f"Updated line with external_id {external_id}")
                        synced_count += 1
                    else:
                        self.env['infrastructure.line'].with_context(from_sync=True).create(line_data)
                        _logger.info(f"Created line with external_id {external_id}")
                        synced_count += 1

                result['lines'] = {'synced': synced_count, 'skipped': skipped_count}
                result['messages'].append(f"Lines sync completed: {synced_count} synced, {skipped_count} skipped")

                # Update last sync timestamp
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.last_sync', current_time)

            # Sync line stations if requested
            if sync_line_stations:
                synced_count = 0
                skipped_count = 0
                lines = self.env['infrastructure.line'].search([('external_id', '!=', False)])
                existing_ls = self.env['infrastructure.line.station'].search([('external_id', '!=', False)])
                existing_ls_map = {ls.external_id: ls for ls in existing_ls}
                directions = ['GOING', 'RETURNING']

                for line in lines:
                    for direction in directions:
                        api_url = f'http://147.93.52.105:9000/infra/linestation?lineId={line.external_id}&direction={direction}'
                        _logger.info("Fetching line stations for line %s (external_id: %s, direction: %s) from API: %s",
                                     line.enterprise_code, line.external_id, direction, api_url)
                        try:
                            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=30)
                            if response.status_code != 200:
                                _logger.error("Failed to fetch line stations for line %s, direction %s: %s (Status: %s)",
                                              line.external_id, direction, response.text, response.status_code)
                                skipped_count += 1
                                continue

                            line_stations = response.json()
                            if not isinstance(line_stations, list):
                                _logger.warning("Invalid API response for line %s, direction %s: Expected list",
                                                line.external_id, direction)
                                skipped_count += 1
                                continue

                            _logger.info("API returned %s line stations for line %s (external_id: %s, direction: %s)",
                                         len(line_stations), line.enterprise_code, line.external_id, direction)

                            for ls in line_stations:
                                external_id = ls.get('id')
                                if not external_id:
                                    _logger.warning("Skipping line station with missing id for line %s, direction %s: %s",
                                                    line.external_id, direction, ls)
                                    skipped_count += 1
                                    continue

                                line_id = ls.get('line', {}).get('id')
                                station_id = ls.get('station', {}).get('id')
                                if not line_id or not station_id:
                                    _logger.warning("Skipping incomplete line station with external_id %s for line %s, direction %s",
                                                    external_id, line.external_id, direction)
                                    skipped_count += 1
                                    continue

                                line_record = self.env['infrastructure.line'].search([('external_id', '=', line_id)], limit=1)
                                station = self.env['infrastructure.station'].search([('external_id', '=', station_id)], limit=1)
                                if not line_record or not station:
                                    _logger.warning("Skipping line station %s: Line %s or station %s not found",
                                                    external_id, line_id, station_id)
                                    skipped_count += 1
                                    continue

                                ls_data = {
                                    'line_id': line_record.id,
                                    'station_id': station.id,
                                    'order': ls.get('order', 0),
                                    'stop_duration': ls.get('stopDuration', 0),
                                    'direction': ls.get('direction', 'GOING').upper(),
                                    'radius': ls.get('radius', 0),
                                    'lat': float(ls.get('lat', 0.0)),
                                    'lng': float(ls.get('lng', 0.0)),
                                    'alertable': ls.get('alertable', False),
                                    'efficient': ls.get('efficient', False),
                                    'duration': ls.get('duration', 0),
                                    'external_id': external_id,
                                    'location_picker': True
                                }

                                api_data_serialized = self.env['infrastructure.line.station']._serialize_line_station_data(
                                    ls, line_record.id, station.id
                                )
                                existing_ls = existing_ls_map.get(external_id)

                                if existing_ls:
                                    existing_data_serialized = self.env['infrastructure.line.station']._serialize_existing_line_station(existing_ls)
                                    if existing_data_serialized == api_data_serialized:
                                        _logger.debug("Skipping line station with external_id %s: No changes", external_id)
                                        skipped_count += 1
                                        continue
                                    existing_ls.with_context(from_sync=True).write(ls_data)
                                    _logger.info("Updated line station with external_id %s for line %s, direction %s",
                                                 external_id, line.external_id, direction)
                                    synced_count += 1
                                else:
                                    self.env['infrastructure.line.station'].with_context(from_sync=True).create(ls_data)
                                    _logger.info("Created line station with external_id %s for line %s, direction %s",
                                                 external_id, line.external_id, direction)
                                    synced_count += 1

                        except requests.RequestException as e:
                            _logger.error("API request failed for line %s, direction %s: %s", line.external_id, direction, str(e))
                            skipped_count += 1
                            continue

                result['line_stations'] = {'synced': synced_count, 'skipped': skipped_count}
                result['messages'].append(f"Line stations sync completed: {synced_count} synced, {skipped_count} skipped")

                # Update last sync timestamp
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.station.last_sync', current_time)

            return result

        except Exception as e:
            _logger.error("Infrastructure sync failed: %s", str(e))
            raise UserError(f"Infrastructure sync failed: {str(e)}")

    @api.model
    def _serialize_station_data(self, station_data, line_ids):
        """
        Serialize station data for comparison to detect changes.
        :param station_data: Dict with station data (name_ar, name_en, etc.)
        :param line_ids: List of line IDs
        :return: JSON string for comparison
        """
        data = {
            'name_ar': station_data.get('nameAr', ''),
            'name_en': station_data.get('nameEn', ''),
            'name_fr': station_data.get('nameFr', ''),
            'latitude': float(station_data.get('lat', 0.0)),
            'longitude': float(station_data.get('lng', 0.0)),
            'paths': station_data.get('paths', []) or [],
            'changes': station_data.get('changes', {}) or {},
            'schedule': station_data.get('schedule', []) or [],
            'line_ids': sorted(line_ids)  # Sort for consistent comparison
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _serialize_existing_station(self, station):
        """
        Serialize existing station record for comparison.
        :param station: infrastructure.station record
        :return: JSON string for comparison
        """
        data = {
            'name_ar': station.name_ar,
            'name_en': station.name_en,
            'name_fr': station.name_fr,
            'latitude': station.latitude,
            'longitude': station.longitude,
            'paths': json.loads(station.paths) if station.paths else [],
            'changes': json.loads(station.changes) if station.changes else {},
            'schedule': json.loads(station.schedule) if station.schedule else [],
            'line_ids': sorted(station.line_ids.ids)  # Sort for consistent comparison
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _sync_stations_from_api(self):
        """Internal method to sync stations from API"""
        api_url = 'http://147.93.52.105:9000/infra/station'
        _logger.info("Fetching all stations from API: %s", api_url)

        try:
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code != 200:
                raise UserError(f"Failed to fetch stations from API: {response.text} (Status: {response.status_code})")

            stations = response.json()
            _logger.info("API returned %s stations", len(stations))
            
            # Update last sync timestamp
            current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            self.env['ir.config_parameter'].sudo().set_param('infrastructure.station.last_sync', current_time)

            synced_count = 0
            skipped_count = 0
            api_station_ids = set()

            # Get existing stations
            existing_stations = self.search([])
            existing_station_map = {station.external_id: station for station in existing_stations if station.external_id}

            for station in stations:
                try:
                    external_id = station.get('id')
                    if not external_id:
                        _logger.warning("Skipping station with missing id: %s", station)
                        skipped_count += 1
                        continue

                    name_ar = station.get('nameAr', '')
                    name_en = station.get('nameEn', '')
                    name_fr = station.get('nameFr', '')
                    
                    # Skip test or incomplete stations
                    if (
                        any(name.lower().startswith('test') for name in [name_ar, name_en, name_fr]) or
                        not all([name_ar, name_en, name_fr])
                    ):
                        _logger.info(f"Skipping test or incomplete station with external_id {external_id}")
                        skipped_count += 1
                        continue

                    # Prepare line IDs
                    line_ids = []
                    for line_id in station.get('lines', []):
                        line = self.env['infrastructure.line'].search([('external_id', '=', line_id)], limit=1)
                        if line:
                            line_ids.append(line.id)

                    # Prepare station data
                    station_data = {
                        'name_ar': name_ar,
                        'name_en': name_en,
                        'name_fr': name_fr,
                        'latitude': float(station.get('lat', 36.7538)),
                        'longitude': float(station.get('lng', 3.0588)),
                        'paths': json.dumps(station.get('paths', [])),
                        'changes': json.dumps(station.get('changes', {}) or {}),
                        'schedule': json.dumps(station.get('schedule', [])),
                        'line_ids': [(6, 0, line_ids)],
                        'external_id': external_id,
                        'location_picker': True
                    }

                    # Serialize API data for comparison
                    api_data_serialized = self._serialize_station_data(station, line_ids)

                    api_station_ids.add(external_id)

                    # Update or create station
                    existing_station = existing_station_map.get(external_id)
                    if existing_station:
                        # Serialize existing station for comparison
                        existing_data_serialized = self._serialize_existing_station(existing_station)
                        if existing_data_serialized == api_data_serialized:
                            _logger.debug(f"Skipping station with external_id {external_id}: No changes")
                            skipped_count += 1
                            continue

                        existing_station.with_context(from_sync=True).write(station_data)
                        _logger.info(f"Updated station with external_id {external_id}")
                        synced_count += 1
                    else:
                        self.with_context(from_sync=True).create(station_data)
                        _logger.info(f"Created station with external_id {external_id}")
                        synced_count += 1

                except Exception as e:
                    _logger.error(f"Failed to process station {station.get('id', 'Unknown')}: {str(e)}")
                    skipped_count += 1

            # Handle station deletion
            stations_to_delete = [
                station for station in existing_stations
                if station.external_id and station.external_id not in api_station_ids
            ]

            for station in stations_to_delete:
                try:
                    station.with_context(from_sync=True).unlink()
                    _logger.info(f"Deleted stale station with external_id {station.external_id}")
                except Exception as e:
                    _logger.error(f"Failed to delete stale station {station.external_id}: {str(e)}")
                    skipped_count += 1

            message = f"Stations sync completed: {synced_count} synced, {skipped_count} skipped"
            _logger.info(message)
            
            return {
                'synced': synced_count,
                'skipped': skipped_count,
                'message': message
            }

        except requests.RequestException as e:
            error_message = f"Station sync failed: {str(e)}"
            _logger.error(error_message)
            raise UserError(error_message)