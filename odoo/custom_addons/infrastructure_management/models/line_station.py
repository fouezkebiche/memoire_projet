import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from psycopg2 import OperationalError

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

    def _sync_to_api(self, record):
        """Helper method to sync a record to the API via POST if no external_id exists."""
        if record.external_id:
            return record.external_id

        station = self.env['infrastructure.station'].browse(record.station_id.id)
        line = self.env['infrastructure.line'].browse(record.line_id.id)
        if not line.external_id or not station.external_id:
            raise UserError("Cannot sync to API: Line or station missing external_id.")

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
                return external_id
            else:
                raise UserError(f"Failed to create line station in API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")

    @api.model
    def create(self, vals):
        # Check for duplicates
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

        record = super(InfrastructureLineStation, self).create(vals)
        try:
            record._sync_to_api(record)
        except Exception as e:
            _logger.error("Failed to sync line station %s to API: %s", record.id, str(e))
            raise UserError(f"Failed to sync line station to API: {str(e)}")

        return record

    def write(self, vals):
        result = super(InfrastructureLineStation, self).write(vals)
        for record in self:
            if not record.external_id:
                try:
                    record._sync_to_api(record)
                except Exception as e:
                    _logger.error("Failed to sync line station %s to API: %s", record.id, str(e))
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
                # Accept 200, 201, 204 as success, or check response text
                if response.status_code in (200, 201, 204) or "updated successfully" in response.text.lower():
                    _logger.info("Line station %s updated successfully in API", record.external_id)
                else:
                    _logger.error("API PUT failed: %s (Status: %s)", response.text, response.status_code)
                    raise UserError(f"Failed to update line station in API: {response.text} (Status: {response.status_code})")
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(f"API request failed: {str(e)}")

        return result

    def unlink(self):
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
                        _logger.warning("API DELETE failed: %s (Status: %s)", response.text, response.status_code)
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed: %s", str(e))
                    raise UserError(f"API DELETE request failed: {str(e)}")

        return super(InfrastructureLineStation, self).unlink()

    @api.model
    def clean_duplicates(self):
        _logger.info("Cleaning duplicate line stations")
        records = self.search([
            ('line_id', '!=', False),
            ('direction', '!=', False),
            ('order', '!=', False)
        ], order='line_id, direction, order, id')
        seen_keys = set()
        for record in records:
            key = (record.line_id.id, record.direction, record.order)
            if key in seen_keys:
                _logger.info("Deleting duplicate line station id %s (line %s, %s, order %s)",
                             record.id, record.line_id.enterprise_code, record.direction, record.order)
                record.unlink()
            else:
                seen_keys.add(key)

    @api.model
    def sync_linestations_from_api(self):
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                with self.env.cr.savepoint():
                    self.clean_duplicates()
                    lines = self.env['infrastructure.line'].search([])
                    if not lines:
                        raise UserError("No lines found. Sync lines first.")

                    base_api_url = 'http://147.93.52.105:9000/infra/linestation'
                    directions = ['GOING', 'RETURNING']
                    created_count = 0

                    for line in lines:
                        for direction in directions:
                            params = {'lineId': line.external_id, 'direction': direction}
                            try:
                                response = requests.get(
                                    base_api_url,
                                    headers={'Content-Type': 'application/json'},
                                    params=params,
                                    timeout=30
                                )
                                _logger.info("API GET %s response: %s (Status: %s)", base_api_url, response.text, response.status_code)
                                if response.status_code == 200:
                                    line_stations = response.json()
                                    for ls in line_stations:
                                        if not ls.get('line') or not ls.get('station'):
                                            _logger.warning("Skipping line station with missing data: %s", ls.get('id', 'Unknown'))
                                            continue

                                        line_record = self.env['infrastructure.line'].search(
                                            [('external_id', '=', ls['line'].get('id'))], limit=1
                                        )
                                        station = self.env['infrastructure.station'].search(
                                            [('external_id', '=', ls['station'].get('id'))], limit=1
                                        )
                                        if not line_record or not station:
                                            _logger.warning("Line or station not found for line station %s", ls.get('id', 'Unknown'))
                                            continue

                                        # Check for existing record
                                        existing = self.search([
                                            ('line_id', '=', line_record.id),
                                            ('direction', '=', ls.get('direction')),
                                            ('order', '=', ls.get('order', 0))
                                        ], limit=1)
                                        if existing:
                                            _logger.info("Skipping duplicate line station for line %s, %s, order %s",
                                                         line_record.enterprise_code, ls.get('direction'), ls.get('order'))
                                            continue

                                        ls_data = {
                                            'order': ls.get('order', 0),
                                            'stop_duration': ls.get('stopDuration', 0),
                                            'direction': ls.get('direction'),
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

                                        self.create(ls_data)
                                        created_count += 1
                                        _logger.info("Created line station %s for line %s, %s",
                                                     ls.get('id'), line_record.enterprise_code, ls.get('direction'))
                                else:
                                    _logger.warning("API GET failed: %s (Status: %s)", response.text, response.status_code)
                            except requests.RequestException as e:
                                _logger.error("API GET failed: %s", str(e))
                                continue

                    _logger.info("Synced %s line stations", created_count)
                    return {'created': created_count}
            except OperationalError as e:
                if 'could not serialize access' in str(e):
                    retry_count += 1
                    _logger.warning("Transaction conflict, retrying (%s/%s)", retry_count, max_retries)
                    if retry_count >= max_retries:
                        raise UserError("Failed to sync after retries: Transaction conflict.")
                    continue
                raise
            except Exception as e:
                _logger.error("Sync failed: %s", str(e))
                raise UserError(f"Sync failed: {str(e)}")