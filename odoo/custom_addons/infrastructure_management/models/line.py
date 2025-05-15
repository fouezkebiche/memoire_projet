import requests
import json
import logging
import re
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
    color = fields.Char(string='Color', required=True, default='#FF0000')  # Reverted to Char
    enterprise_code = fields.Char(string='Enterprise Code', required=True)
    line_type = fields.Selection(
        [('1', 'Bus'), ('2', 'Metro'), ('3', 'Tram')],
        string='Line Type',
        default='1',
        required=True
    )
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

    def name_get(self):
        result = []
        for line in self:
            name = line.enterprise_code or line.code or f'Line {line.id}'
            _logger.debug("name_get for line ID %s: %s", line.id, name)
            result.append((line.id, name))
        return result

    @api.constrains('color')
    def _check_color(self):
        for record in self:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', record.color):
                raise ValidationError("Color must be a valid hex code (e.g., #FF0000).")

    def _prepare_station_data(self, station):
        return {
            'id': station.external_id or station.id,
            'nameAr': station.name_ar or '',
            'nameEn': station.name_en or '',
            'nameFr': station.name_fr or '',
            'lat': station.latitude or 0.0,
            'lng': station.longitude or 0.0,
            'paths': json.loads(station.paths) if station.paths else [],
            'lines': [line.external_id or line.id for line in station.line_ids],
            'schedule': json.loads(station.schedule) if station.schedule else [],
            'changes': None  # Align with API response
        }

    @api.model
    def create(self, vals):
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., '[\"08:00\", \"09:00\"]').")

        # Validate color format
        if 'color' in vals:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', vals['color']):
                raise UserError("Color must be a valid hex code (e.g., #FF0000).")

        with self.env.cr.savepoint():
            record = super(InfrastructureLine, self).create(vals)

        departure_station = self.env['infrastructure.station'].browse(record.departure_station_id.id)
        terminus_station = self.env['infrastructure.station'].browse(record.terminus_station_id.id)

        api_data = {
            'code': record.code,
            'color': record.color,  # Use hex code directly
            'lineType': int(record.line_type),
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
                        raise ValueError("No external_id found in JSON response")
                except json.JSONDecodeError:
                    response_text = response.text.strip()
                    if "Line created with id:" in response_text:
                        try:
                            external_id = int(response_text.split("Line created with id:")[1].strip())
                        except (IndexError, ValueError):
                            _logger.error("Unable to parse external_id from text response: %s", response_text)
                            raise UserError(f"Failed to parse external_id from API response: {response_text}")
                    else:
                        _logger.error("Unexpected response format: %s", response_text)
                        raise UserError(f"Unexpected API response format: {response_text}")

                self._cr.execute('UPDATE infrastructure_line SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to line %s", external_id, record.enterprise_code or record.code)
            else:
                _logger.warning("Failed to create line in API: %s (Status: %s). Line created in Odoo.", response.text, response.status_code)
        except (requests.RequestException, UserError) as e:
            _logger.error("API POST request failed: %s. Line created in Odoo without external_id.", str(e))

        return record

    def write(self, vals):
        if 'color' in vals:
            if not re.match(r'^#[0-9A-Fa-f]{6}$', vals['color']):
                raise UserError("Color must be a valid hex code (e.g., #FF0000).")

        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError("Schedule must be valid JSON (e.g., '[\"08:00\", \"09:00\"]').")

        result = super(InfrastructureLine, self).write(vals)

        for record in self:
            if not record.external_id:
                _logger.warning("Skipping API update for line %s: No external_id.", record.enterprise_code or record.code)
                continue

            departure_station = self.env['infrastructure.station'].browse(record.departure_station_id.id)
            terminus_station = self.env['infrastructure.station'].browse(record.terminus_station_id.id)

            api_data = {
                'code': record.code,
                'color': record.color,
                'lineType': int(record.line_type),
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
                            record.enterprise_code or record.code, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for line %s: %s.", 
                                 record.enterprise_code or record.code, str(e))
            else:
                _logger.info("Skipping API delete for line %s: No external_id.", record.enterprise_code or record.code)

        return super(InfrastructureLine, self).unlink()

    @api.model
    def sync_lines_from_api(self):
        try:
            self.env['infrastructure.station'].sync_stations_from_api()
        except Exception as e:
            _logger.error("Failed to sync stations: %s", str(e))
            self.env['mail.activity'].create({
                'res_model': 'ir.cron',
                'res_id': self.env.ref('infrastructure_management.cron_sync_lines').id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                'summary': 'Line Sync Failure',
                'note': f'Failed to sync stations: {str(e)}',
                'user_id': self.env.ref('base.user_admin').id,
            })
            raise UserError(f"Failed to sync stations: {str(e)}")

        api_url = 'http://147.93.52.105:9000/infra/line'
        last_sync = self.env['ir.config_parameter'].sudo().get_param('infrastructure.line.last_sync')
        params = {}
        if last_sync:
            params['last_updated'] = last_sync
            _logger.info("Incremental sync for lines since %s", last_sync)

        _logger.info("Sending GET request to: %s with params: %s", api_url, params)

        try:
            response = requests.get(
                api_url,
                headers={'Content-Type': 'application/json'},
                params=params,
                timeout=30
            )
            _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            if response.status_code == 200:
                lines = response.json()
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.last_sync', current_time)

                synced_count = 0
                skipped_count = 0
                for line in lines:
                    try:
                        external_id = line.get('id')
                        if not external_id:
                            _logger.warning("Skipping line with missing id: %s", line)
                            skipped_count += 1
                            continue

                        code = line.get('code', '')
                        enterprise_code = line.get('enterpriseCode', '')
                        if (
                            code.lower().startswith('test') or
                            enterprise_code.lower().startswith('test') or
                            not line.get('departureStation') or
                            not line.get('terminusStation')
                        ):
                            _logger.info(f"Skipping test line with external_id {external_id}")
                            skipped_count += 1
                            continue

                        if not code or not enterprise_code:
                            _logger.warning("Skipping line with missing code or enterpriseCode: %s", line)
                            skipped_count += 1
                            continue

                        departure_station_id = line.get('departureStation', {}).get('id')
                        if not departure_station_id:
                            _logger.warning("Skipping line with missing departureStation id: %s", code)
                            skipped_count += 1
                            continue
                        departure_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', departure_station_id)], limit=1
                        )
                        if not departure_station:
                            with self.env.cr.savepoint():
                                departure_station = self.env['infrastructure.station'].create({
                                    'name_ar': line['departureStation'].get('nameAr', 'Unknown'),
                                    'name_en': line['departureStation'].get('nameEn', 'Unknown'),
                                    'name_fr': line['departureStation'].get('nameFr', 'Unknown'),
                                    'latitude': line['departureStation'].get('lat', 0.0),
                                    'longitude': line['departureStation'].get('lng', 0.0),
                                    'external_id': departure_station_id,
                                    'paths': json.dumps(line['departureStation'].get('paths', [])),
                                    'schedule': json.dumps(line['departureStation'].get('schedule', [])),
                                    'changes': json.dumps({})  # Align with API
                                })

                        terminus_station_id = line.get('terminusStation', {}).get('id')
                        if not terminus_station_id:
                            _logger.warning("Skipping line with missing terminusStation id: %s", code)
                            skipped_count += 1
                            continue
                        terminus_station = self.env['infrastructure.station'].search(
                            [('external_id', '=', terminus_station_id)], limit=1
                        )
                        if not terminus_station:
                            with self.env.cr.savepoint():
                                terminus_station = self.env['infrastructure.station'].create({
                                    'name_ar': line['terminusStation'].get('nameAr', 'Unknown'),
                                    'name_en': line['terminusStation'].get('nameEn', 'Unknown'),
                                    'name_fr': line['terminusStation'].get('nameFr', 'Unknown'),
                                    'latitude': line['terminusStation'].get('lat', 0.0),
                                    'longitude': line['terminusStation'].get('lng', 0.0),
                                    'external_id': terminus_station_id,
                                    'paths': json.dumps(line['terminusStation'].get('paths', [])),
                                    'schedule': json.dumps(line['terminusStation'].get('schedule', [])),
                                    'changes': json.dumps({})  # Align with API
                                })

                        color = line.get('color', '#FF0000')
                        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
                            _logger.warning("Invalid color format for line %s: %s. Using default #FF0000.", code, color)
                            color = '#FF0000'

                        schedule = json.dumps(line.get('schedule', []))
                        try:
                            json.loads(schedule)
                        except json.JSONDecodeError:
                            _logger.warning("Invalid schedule format for line %s: %s. Using empty schedule.", code, schedule)
                            schedule = '[]'

                        line_data = {
                            'code': code,
                            'color': color,
                            'line_type': str(line.get('lineType', 1)),
                            'enterprise_code': enterprise_code,
                            'departure_station_id': departure_station.id,
                            'terminus_station_id': terminus_station.id,
                            'schedule': schedule,
                            'external_id': external_id
                        }

                        with self.env.cr.savepoint():
                            existing_line = self.search([('external_id', '=', external_id)], limit=1)
                            if existing_line:
                                existing_line.write(line_data)
                                _logger.info("Updated line %s", external_id)
                            else:
                                self.create(line_data)
                                _logger.info("Created line %s", external_id)
                            synced_count += 1

                    except Exception as e:
                        _logger.error("Failed to sync line %s: %s", line.get('id', 'Unknown'), str(e))
                        skipped_count += 1
                        continue

                if skipped_count > 5:
                    self.env['mail.activity'].create({
                        'res_model': 'ir.cron',
                        'res_id': self.env.ref('infrastructure_management.cron_sync_lines').id,
                        'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                        'summary': 'Excessive Lines Skipped',
                        'note': f'Skipped {skipped_count} lines during sync. Check API data.',
                        'user_id': self.env.ref('base.user_admin').id,
                    })

                message = f"Synced {synced_count} lines, skipped {skipped_count} lines."
                _logger.info(message)
                return {
                    'synced': synced_count,
                    'skipped': skipped_count,
                    'message': message
                }

            else:
                raise UserError(f"Failed to fetch lines from API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("Line sync failed: %s", str(e))
            self.env['mail.activity'].create({
                'res_model': 'ir.cron',
                'res_id': self.env.ref('infrastructure_management.cron_sync_lines').id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                'summary': 'Line Sync Failure',
                'note': f'Sync failed: {str(e)}',
                'user_id': self.env.ref('base.user_admin').id,
            })
            raise UserError(f"Line sync failed: {str(e)}")