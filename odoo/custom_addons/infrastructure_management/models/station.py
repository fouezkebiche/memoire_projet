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
    external_id = fields.Integer(string='External API ID', readonly=True)
    location_picker = fields.Boolean(string='Location Picker', default=True)  # Dummy field for widget

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
    def sync_stations_from_api(self):
        api_url = 'http://147.93.52.105:9000/infra/station'
        last_sync = self.env['ir.config_parameter'].sudo().get_param('infrastructure.station.last_sync')
        params = {}
        if last_sync:
            params['last_updated'] = last_sync
            _logger.info("Incremental sync for stations since %s", last_sync)

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
                stations = response.json()
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.station.last_sync', current_time)

                synced_count = 0
                skipped_count = 0
                api_station_ids = set()

                for station in stations:
                    try:
                        external_id = station.get('id')
                        if not external_id:
                            _logger.warning("Skipping station with missing id: %s", station)
                            skipped_count += 1
                            continue

                        api_station_ids.add(external_id)

                        name_ar = station.get('nameAr', '')
                        name_en = station.get('nameEn', '')
                        name_fr = station.get('nameFr', '')
                        if not name_ar or not name_en or not name_fr:
                            _logger.warning("Skipping station with missing required name fields: %s", station)
                            skipped_count += 1
                            continue

                        line_ids = []
                        for line_id in station.get('lines', []):
                            line = self.env['infrastructure.line'].search(
                                [('external_id', '=', line_id)], limit=1
                            )
                            if line:
                                line_ids.append(line.id)
                            else:
                                _logger.warning("Line with external_id %s not found for station %s", line_id, external_id)

                        paths = json.dumps(station.get('paths', []))
                        changes = json.dumps(station.get('changes', {}) if station.get('changes') is not None else {})
                        schedule = json.dumps(station.get('schedule', []))
                        for field, value in [('paths', paths), ('changes', changes), ('schedule', schedule)]:
                            try:
                                json.loads(value)
                            except json.JSONDecodeError:
                                _logger.warning("Invalid %s format for station %s: %s. Using default.", field, external_id, value)
                                if field == 'paths':
                                    paths = '[]'
                                elif field == 'changes':
                                    changes = '{}'
                                elif field == 'schedule':
                                    schedule = '[]'

                        station_data = {
                            'name_ar': name_ar,
                            'name_en': name_en,
                            'name_fr': name_fr,
                            'latitude': float(station.get('lat', 0.0)),
                            'longitude': float(station.get('lng', 0.0)),
                            'paths': paths,
                            'changes': changes,
                            'schedule': schedule,
                            'line_ids': [(6, 0, line_ids)],
                            'external_id': external_id
                        }

                        with self.env.cr.savepoint():
                            existing_station = self.search([('external_id', '=', external_id)], limit=1)
                            if existing_station:
                                existing_station.write(station_data)
                                _logger.info("Updated station %s", external_id)
                            else:
                                self.create(station_data)
                                _logger.info("Created station %s", external_id)
                            synced_count += 1

                    except Exception as e:
                        _logger.error("Failed to sync station %s: %s", station.get('id', 'Unknown'), str(e))
                        skipped_count += 1
                        continue

                odoo_stations = self.search([('external_id', '!=', False)])
                for station in odoo_stations:
                    if station.external_id not in api_station_ids:
                        try:
                            station.unlink()
                            _logger.info("Deleted stale station with external_id %s", station.external_id)
                        except Exception as e:
                            _logger.error("Failed to delete stale station %s: %s", station.external_id, str(e))

                if skipped_count > 10:
                    self.env['mail.activity'].create({
                        'res_model': 'ir.cron',
                        'res_id': self.env.ref('infrastructure_management.cron_sync_stations').id,
                        'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                        'summary': 'Excessive Stations Skipped',
                        'note': f'Skipped {skipped_count} stations during sync. Check API data.',
                        'user_id': self.env.ref('base.user_admin').id,
                    })

                message = f"Synced {synced_count} stations, skipped {skipped_count} stations."
                _logger.info(message)
                return {
                    'synced': synced_count,
                    'skipped': skipped_count,
                    'message': message
                }

            else:
                raise UserError(f"Failed to fetch stations from API: {response.text} (Status: {response.status_code})")
        except requests.RequestException as e:
            _logger.error("Station sync failed: %s", str(e))
            self.env['mail.activity'].create({
                'res_model': 'ir.cron',
                'res_id': self.env.ref('infrastructure_management.cron_sync_stations').id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                'summary': 'Station Sync Failure',
                'note': f'Sync failed: {str(e)}',
                'user_id': self.env.ref('base.user_admin').id,
            })
            raise UserError(f"Station sync failed: {str(e)}")