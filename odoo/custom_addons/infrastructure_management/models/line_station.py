import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

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
    external_id = fields.Integer(string='External API ID', readonly=True, index=True)
    location_picker = fields.Boolean(string='Location Picker', default=True)

    @api.constrains('lat', 'lng')
    def _check_coordinates(self):
        for record in self:
            if record.lat and (record.lat < -90 or record.lat > 90):
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
            if record.lng and (record.lng < -180 or record.lng > 180):
                raise ValidationError("Longitude must be between -180 and 180 degrees.")

    @api.constrains('order', 'line_id', 'direction')
    def _check_unique_order(self):
        for record in self:
            duplicates = self.search([
                ('line_id', '=', record.line_id.id),
                ('direction', '=', record.direction),
                ('order', '=', record.order),
                ('id', '!=', record.id)
            ])
            if duplicates:
                raise ValidationError(
                    f"Order {record.order} is already used for line {record.line_id.enterprise_code} "
                    f"in direction {record.direction}."
                )

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

    def _prepare_line_data(self, line):
        departure_station = line.departure_station_id
        terminus_station = line.terminus_station_id
        return {
            'id': line.external_id or line.id,
            'code': line.code or 'LINE',
            'color': line.color or '#000000',
            'departureStation': departure_station.name_en or 'Unknown' if departure_station else 'Unknown',
            'departureAddress': departure_station.name_en or 'Unknown' if departure_station else 'Unknown',
            'terminusStation': terminus_station.name_en or 'Unknown' if terminus_station else 'Unknown',
            'terminusAddress': terminus_station.name_en or 'Unknown' if terminus_station else 'Unknown',
            'schedule': json.loads(line.schedule) if line.schedule else ['08:00']
        }

    @api.model
    def create(self, vals):
        line_id = vals.get('line_id')
        direction = vals.get('direction')
        order = vals.get('order')
        if line_id and direction and order:
            existing = self.search([
                ('line_id', '=', line_id),
                ('direction', '=', direction),
                ('order', '=', order)
            ])
            if existing:
                raise UserError(
                    f"Order {order} is already used for line {existing.line_id.enterprise_code} "
                    f"in direction {direction}."
                )

        # During sync, skip API POST and just create the record in Odoo
        if self._context.get('from_sync'):
            _logger.info("Creating line station in Odoo from sync: line_id=%s, station_id=%s (external_id: %s)",
                         vals.get('line_id'), vals.get('station_id'), vals.get('external_id'))
            return super(InfrastructureLineStation, self).create(vals)

        record = super(InfrastructureLineStation, self).create(vals)

        station = self.env['infrastructure.station'].browse(record.station_id.id)
        line = self.env['infrastructure.line'].browse(record.line_id.id)
        if not line.external_id or not station.external_id:
            _logger.warning("Skipping API POST for line station %s: Line or station missing external_id.", record.id)
            return record

        api_data = {
            'order': record.order,
            'stopDuration': record.stop_duration,
            'direction': record.direction,
            'radius': record.radius,
            'lat': record.lat or station.latitude or 0.0,
            'lng': record.lng or station.longitude or 0.0,
            'line': self._prepare_line_data(line),
            'station': self._prepare_station_data(station),
            'alertable': record.alertable,
            'efficient': record.efficient,
            'duration': record.duration
        }

        try:
            api_url = 'http://147.93.52.105:9000/infra/linestation'
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
                    if "Line Station created with id:" in response_text:
                        try:
                            external_id = int(response_text.split("Line Station created with id:")[1].strip())
                        except (IndexError, ValueError):
                            raise UserError(f"Failed to parse external_id from response: {response_text}")
                    else:
                        raise UserError(f"Unexpected API response format: {response_text}")
                
                self._cr.execute('UPDATE infrastructure_line_station SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to line station %s", external_id, record.id)
            else:
                raise UserError(f"Failed to create line station in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

        return record

    def write(self, vals):
        # Skip API update during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API update for line station during sync: %s", self.id)
            return super(InfrastructureLineStation, self).write(vals)

        result = super(InfrastructureLineStation, self).write(vals)

        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for line station %s: No external_id.", record.id)
                continue

            station = self.env['infrastructure.station'].browse(record.station_id.id)
            line = self.env['infrastructure.line'].browse(record.line_id.id)
            api_data = {
                'order': record.order,
                'stopDuration': record.stop_duration,
                'direction': record.direction,
                'radius': record.radius,
                'lat': record.lat or station.latitude or 0.0,
                'lng': record.lng or station.longitude or 0.0,
                'line': self._prepare_line_data(line),
                'station': self._prepare_station_data(station),
                'alertable': record.alertable,
                'efficient': record.efficient,
                'duration': record.duration
            }

            try:
                api_url = f'http://147.93.52.105:9000/infra/linestation/{record.external_id}'
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
                    raise UserError(f"Failed to update line station in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
        # Skip API delete during sync
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for line station during sync: %s", self.id)
            return super(InfrastructureLineStation, self).unlink()

        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:9000/infra/linestation/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete line station %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.id, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for line station %s: %s.", record.id, str(e))
            else:
                _logger.info("Skipping API delete for line station %s: No external_id.", record.id)

        return super(InfrastructureLineStation, self).unlink()

    @api.model
    def _serialize_line_station_data(self, ls_data, line_id, station_id):
        """
        Serialize line station data for comparison to detect changes.
        :param ls_data: Dict with line station data (order, direction, etc.)
        :param line_id: ID of the line
        :param station_id: ID of the station
        :return: JSON string for comparison
        """
        data = {
            'order': ls_data.get('order', 0),
            'stop_duration': ls_data.get('stopDuration', 0),
            'direction': ls_data.get('direction', 'GOING'),
            'radius': ls_data.get('radius', 0),
            'lat': float(ls_data.get('lat', 0.0)),
            'lng': float(ls_data.get('lng', 0.0)),
            'alertable': ls_data.get('alertable', False),
            'efficient': ls_data.get('efficient', False),
            'duration': ls_data.get('duration', 0),
            'line_id': line_id,
            'station_id': station_id
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _serialize_existing_line_station(self, ls):
        """
        Serialize existing line station record for comparison.
        :param ls: infrastructure.line.station record
        :return: JSON string for comparison
        """
        data = {
            'order': ls.order,
            'stop_duration': ls.stop_duration,
            'direction': ls.direction,
            'radius': ls.radius,
            'lat': ls.lat,
            'lng': ls.lng,
            'alertable': ls.alertable,
            'efficient': ls.efficient,
            'duration': ls.duration,
            'line_id': ls.line_id.id if ls.line_id else False,
            'station_id': ls.station_id.id if ls.station_id else False
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _sync_line_stations_from_api(self):
        _logger.info("Starting line stations sync from API")

        lines = self.env['infrastructure.line'].search([('external_id', '!=', False)])
        if not lines:
            _logger.warning("No lines with external_id found for line station sync")
            return {
                'synced': 0,
                'skipped': 0,
                'message': "No lines available to sync line stations"
            }

        synced_count = 0
        skipped_count = 0
        api_ls_ids = set()

        existing_ls = self.search([])
        existing_ls_map = {ls.external_id: ls for ls in existing_ls if ls.external_id}

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

                    try:
                        line_stations = response.json()
                    except json.JSONDecodeError:
                        _logger.error("Failed to parse JSON response for line %s, direction %s: %s",
                                    line.external_id, direction, response.text)
                        skipped_count += 1
                        continue

                    if line_stations is None:
                        _logger.warning("API returned None for line %s, direction %s", line.external_id, direction)
                        skipped_count += 1
                        continue

                    if not isinstance(line_stations, list):
                        _logger.warning("Invalid API response for line %s, direction %s: Expected list, got %s",
                                        line.external_id, direction, type(line_stations).__name__)
                        skipped_count += 1
                        continue

                    _logger.info("API returned %s line stations for line %s (external_id: %s, direction: %s)",
                                len(line_stations), line.enterprise_code, line.external_id, direction)

                    for ls in line_stations:
                        try:
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

                            api_data_serialized = self._serialize_line_station_data(ls, line_record.id, station.id)
                            existing_ls_record = existing_ls_map.get(external_id)

                            if existing_ls_record:
                                existing_data_serialized = self._serialize_existing_line_station(existing_ls_record)
                                if existing_data_serialized == api_data_serialized:
                                    _logger.debug("Skipping line station with external_id %s: No changes", external_id)
                                    skipped_count += 1
                                    continue
                                existing_ls_record.with_context(from_sync=True).write(ls_data)
                                _logger.info("Updated line station with external_id %s for line %s, direction %s",
                                            external_id, line.external_id, direction)
                                synced_count += 1
                            else:
                                self.with_context(from_sync=True).create(ls_data)
                                _logger.info("Created line station with external_id %s for line %s, direction %s",
                                            external_id, line.external_id, direction)
                                synced_count += 1

                            api_ls_ids.add(external_id)

                        except Exception as e:
                            _logger.error("Failed to process line station %s for line %s, direction %s: %s",
                                        ls.get('id', 'Unknown'), line.external_id, direction, str(e))
                            skipped_count += 1
                            continue

                except requests.RequestException as e:
                    _logger.error("API request failed for line %s, direction %s: %s", line.external_id, direction, str(e))
                    skipped_count += 1
                    if '404' in str(e):
                        _logger.warning("No line stations available for line %s, direction %s (Status: 404)",
                                        line.external_id, direction)
                    continue

        # Handle line station deletion
        try:
            ls_to_delete = [
                ls for ls in existing_ls
                if ls.external_id and ls.external_id not in api_ls_ids
            ]
        except Exception as e:
            _logger.error("Failed to compute line stations to delete: %s", str(e))
            raise

        for ls in ls_to_delete:
            try:
                ls.with_context(from_sync=True).unlink()
                _logger.info("Deleted stale line station with external_id %s", ls.external_id)
                synced_count += 1
            except Exception as e:
                _logger.error("Failed to delete stale line station %s: %s", ls.external_id, str(e))
                skipped_count += 1

        current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.station.last_sync', current_time)

        message = f"Line stations sync completed: {synced_count} synced, {skipped_count} skipped"
        _logger.info(message)
        
        return {
            'synced': synced_count,
            'skipped': skipped_count,
            'message': message
        }