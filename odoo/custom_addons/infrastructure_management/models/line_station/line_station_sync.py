from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class InfrastructureLineStation(models.Model):
    _inherit = 'infrastructure.line.station'

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
            raise UserError(_("Please select at least one entity to sync (Stations, Lines, or Line Stations)"))

        if sync_line_stations:
            _logger.info("Starting line stations sync from API")

            lines = self.env['infrastructure.line'].search([('external_id', '!=', False)])
            if not lines:
                _logger.warning("No lines with external_id found for line station sync")
                result['line_stations'] = {'synced': 0, 'skipped': 0}
                result['messages'].append("No lines available to sync line stations")
                return result

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

            ls_to_delete = [
                ls for ls in existing_ls
                if ls.external_id and ls.external_id not in api_ls_ids
            ]

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

            result['line_stations'] = {'synced': synced_count, 'skipped': skipped_count}
            result['messages'].append(f"Line stations sync completed: {synced_count} synced, {skipped_count} skipped")

        return result

    @api.model
    def _serialize_line_station_data(self, ls_data, line_id, station_id):
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