import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

class InfrastructureLine(models.Model):
    _name = 'infrastructure.line'
    _description = 'Infrastructure Line'
    _rec_name = 'enterprise_code'

    code = fields.Char(string='Code', required=True)
    color = fields.Char(string='Color', default='#000000')
    line_type = fields.Selection(
        [('1', 'Type 1'), ('2', 'Type 2')],
        string='Line Type',
        default='1'
    )
    enterprise_code = fields.Char(string='Enterprise Code', required=True)
    departure_station_id = fields.Many2one(
        'infrastructure.station',
        string='Departure Station'
    )
    terminus_station_id = fields.Many2one(
        'infrastructure.station',
        string='Terminus Station'
    )
    line_station_ids = fields.One2many(
        'infrastructure.line.station',
        'line_id',
        string='Line Stations'
    )
    schedule = fields.Text(string='Schedule', default='[]')
    external_id = fields.Integer(string='External API ID', readonly=True, index=True)

    @api.constrains('schedule')
    def _check_schedule(self):
        for record in self:
            if record.schedule:
                try:
                    json.loads(record.schedule)
                except json.JSONDecodeError:
                    raise ValidationError("Schedule must be valid JSON (e.g., [\"08:00\", \"12:00\"]).")

    def name_get(self):
        result = []
        for line in self:
            name = line.enterprise_code or line.code or f'Line {line.id}'
            _logger.debug("name_get for line ID %s: %s", line.id, name)
            result.append((line.id, name))
        return result

    @api.model
    def create(self, vals):
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., [\"08:00\", \"12:00\"]).")

        # During sync, skip API POST and just create the record in Odoo
        if self._context.get('from_sync'):
            _logger.info("Creating line in Odoo from sync: %s (external_id: %s)", vals.get('enterprise_code'), vals.get('external_id'))
            return super(InfrastructureLine, self).create(vals)

        record = super(InfrastructureLine, self).create(vals)

        departure_station = record.departure_station_id
        terminus_station = record.terminus_station_id

        api_data = {
            'code': record.code,
            'color': record.color,
            'lineType': int(record.line_type) if record.line_type else 1,
            'enterpriseCode': record.enterprise_code,
            'departureStation': self._prepare_station_data(departure_station) if departure_station else {},
            'terminusStation': self._prepare_station_data(terminus_station) if terminus_station else {},
            'lineStations': [self._prepare_line_station_data(ls) for ls in record.line_station_ids],
            'schedule': json.loads(record.schedule) if record.schedule else []
        }

        try:
            api_url = 'http://147.93.52.105:9000/infra/line'
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
                        raise ValueError("No external_id in JSON response")
                except json.JSONDecodeError:
                    response_text = response.text.strip()
                    if "Line created with id:" in response_text:
                        try:
                            external_id = int(response_text.split("Line created with id:")[1].strip())
                        except (IndexError, ValueError):
                            raise UserError(f"Failed to parse external_id from response: {response_text}")
                    else:
                        raise UserError(f"Unexpected API response format: {response_text}")
                
                self._cr.execute('UPDATE infrastructure_line SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to line %s", external_id, record.enterprise_code)
            else:
                raise UserError(f"Failed to create line in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def _prepare_station_data(self, station):
        return {
            'id': station.external_id or station.id,
            'nameAr': station.name_ar or 'Unknown',
            'nameEn': station.name_en or 'Unknown',
            'nameFr': station.name_fr or 'Unknown',
            'lat': station.latitude or 0.0,
            'lng': station.longitude or 0.0,
            'paths': json.loads(station.paths) if station.paths else [],
            'lines': [line.external_id or line.id for line in station.line_ids],
            'schedule': json.loads(station.schedule) if station.schedule else [],
            'changes': json.loads(station.changes) if station.changes else {}
        }

    def _prepare_line_station_data(self, line_station):
        station = line_station.station_id
        return {
            'order': line_station.order,
            'stopDuration': line_station.stop_duration,
            'direction': line_station.direction,
            'station': self._prepare_station_data(station) if station else {},
            'radius': line_station.radius,
            'lat': line_station.lat or (station.latitude if station else 0.0),
            'lng': line_station.lng or (station.longitude if station else 0.0),
            'alertable': line_station.alertable,
            'efficient': line_station.efficient,
            'duration': line_station.duration
        }

    def write(self, vals):
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., [\"08:00\", \"12:00\"]).")

        result = super(InfrastructureLine, self).write(vals)

        # Skip API update during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API update for line during sync: %s", self.enterprise_code)
            return result

        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for line %s: No external_id.", record.enterprise_code or record.id)
                continue

            departure_station = record.departure_station_id
            terminus_station = record.terminus_station_id

            api_data = {
                'code': record.code,
                'color': record.color,
                'lineType': int(record.line_type) if record.line_type else 1,
                'enterpriseCode': record.enterprise_code,
                'departureStation': self._prepare_station_data(departure_station) if departure_station else {},
                'terminusStation': self._prepare_station_data(terminus_station) if terminus_station else {},
                'lineStations': [self._prepare_line_station_data(ls) for ls in record.line_station_ids],
                'schedule': json.loads(record.schedule) if record.schedule else []
            }

            try:
                api_url = f'http://147.93.52.105:9000/infra/line/{record.external_id}'
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
                    raise UserError(f"Failed to update line in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        # Skip API delete during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for line during sync: %s", self.enterprise_code)
            return super(InfrastructureLine, self).unlink()

        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:9000/infra/line/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete line %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.enterprise_code or record.id, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for line %s: %s.", record.enterprise_code or record.id, str(e))
            else:
                _logger.info("Skipping API delete for line %s: No external_id.", record.enterprise_code or record.id)

        return super(InfrastructureLine, self).unlink()

    @api.model
    def _serialize_line_data(self, line_data, departure_id, terminus_id, line_station_ids):
        """
        Serialize line data for comparison to detect changes.
        :param line_data: Dict with line data (code, color, etc.)
        :param departure_id: ID of departure station
        :param terminus_id: ID of terminus station
        :param line_station_ids: List of line station IDs
        :return: JSON string for comparison
        """
        data = {
            'code': line_data.get('code', ''),
            'color': line_data.get('color', ''),
            'line_type': str(line_data.get('lineType', '')),
            'enterprise_code': line_data.get('enterpriseCode', ''),
            'departure_station_id': departure_id,
            'terminus_station_id': terminus_id,
            'schedule': line_data.get('schedule', []) or [],
            'line_station_ids': sorted(line_station_ids)
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _serialize_existing_line(self, line):
        """
        Serialize existing line record for comparison.
        :param line: infrastructure.line record
        :return: JSON string for comparison
        """
        data = {
            'code': line.code,
            'color': line.color,
            'line_type': line.line_type,
            'enterprise_code': line.enterprise_code,
            'departure_station_id': line.departure_station_id.id if line.departure_station_id else False,
            'terminus_station_id': line.terminus_station_id.id if line.terminus_station_id else False,
            'schedule': json.loads(line.schedule) if line.schedule else [],
            'line_station_ids': sorted(line.line_station_ids.ids)
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _sync_lines_from_api(self):
        """Internal method to sync lines from API"""
        api_url = 'http://147.93.52.105:9000/infra/line'
        _logger.info("Fetching all lines from API: %s", api_url)

        try:
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code != 200:
                raise UserError(f"Failed to fetch lines from API: {response.text} (Status: {response.status_code})")

            lines = response.json()
            _logger.info("API returned %s lines", len(lines))
            
            # Update last sync timestamp
            current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.last_sync', current_time)

            synced_count = 0
            skipped_count = 0
            api_line_ids = set()

            # Get existing lines
            existing_lines = self.search([])
            existing_line_map = {line.external_id: line for line in existing_lines if line.external_id}

            for line in lines:
                try:
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

                    # Find departure and terminus stations
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

                    # Prepare line station data
                    line_station_ids = []
                    for ls in line.get('lineStations', []):
                        if ls.get('station', {}).get('id'):
                            station = self.env['infrastructure.station'].search(
                                [('external_id', '=', ls['station']['id'])], limit=1
                            )
                            if station:
                                ls_record = self.env['infrastructure.line.station'].search([
                                    ('line_id.external_id', '=', external_id),
                                    ('station_id', '=', station.id),
                                    ('order', '=', ls.get('order', 0))
                                ], limit=1)
                                if not ls_record:
                                    ls_record = self.env['infrastructure.line.station'].with_context(from_sync=True).create({
                                        'line_id': False,  # Will be set later
                                        'station_id': station.id,
                                        'order': ls.get('order', 0),
                                        'stop_duration': ls.get('stopDuration', 0),
                                        'direction': ls.get('direction', 'GOING'),
                                        'radius': ls.get('radius', 0),
                                        'lat': ls.get('lat', 0.0),
                                        'lng': ls.get('lng', 0.0),
                                        'alertable': ls.get('alertable', False),
                                        'efficient': ls.get('efficient', False),
                                        'duration': ls.get('duration', 0),
                                        'external_id': ls.get('id')
                                    })
                                line_station_ids.append(ls_record.id)

                    # Prepare line data
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

                    # Serialize API data for comparison
                    api_data_serialized = self._serialize_line_data(
                        line,
                        departure_station.id if departure_station else False,
                        terminus_station.id if terminus_station else False,
                        line_station_ids
                    )

                    api_line_ids.add(external_id)

                    # Update or create line
                    existing_line = existing_line_map.get(external_id)
                    if existing_line:
                        existing_data_serialized = self._serialize_existing_line(existing_line)
                        if existing_data_serialized == api_data_serialized:
                            _logger.debug(f"Skipping line with external_id {external_id}: No changes")
                            skipped_count += 1
                            continue

                        existing_line.with_context(from_sync=True).write(line_data)
                        # Update line stations
                        existing_line.line_station_ids.unlink()
                        for ls_id in line_station_ids:
                            self.env['infrastructure.line.station'].browse(ls_id).write({'line_id': existing_line.id})
                        _logger.info(f"Updated line with external_id {external_id}")
                        synced_count += 1
                    else:
                        new_line = self.with_context(from_sync=True).create(line_data)
                        # Update line stations
                        for ls_id in line_station_ids:
                            self.env['infrastructure.line.station'].browse(ls_id).write({'line_id': new_line.id})
                        _logger.info(f"Created line with external_id {external_id}")
                        synced_count += 1

                except Exception as e:
                    _logger.error(f"Failed to process line {line.get('id', 'Unknown')}: {str(e)}")
                    skipped_count += 1

            # Handle line deletion
            lines_to_delete = [
                line for line in existing_lines
                if line.external_id and line.external_id not in api_line_ids
            ]

            for line in lines_to_delete:
                try:
                    line.with_context(from_sync=True).unlink()
                    _logger.info(f"Deleted stale line with external_id {line.external_id}")
                except Exception as e:
                    _logger.error(f"Failed to delete stale line {line.external_id}: {str(e)}")
                    skipped_count += 1

            message = f"Lines sync completed: {synced_count} synced, {skipped_count} skipped"
            _logger.info(message)
            
            return {
                'synced': synced_count,
                'skipped': skipped_count,
                'message': message
            }

        except requests.RequestException as e:
            error_message = f"Line sync failed: {str(e)}"
            _logger.error(error_message)
            raise UserError(error_message)