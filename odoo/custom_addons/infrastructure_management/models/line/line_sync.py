from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class InfrastructureLine(models.Model):
    _inherit = 'infrastructure.line'

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

        try:
            if sync_lines:
                api_url = 'http://147.93.52.105:9000/infra/line'
                _logger.info("Fetching all lines from API: %s", api_url)

                response = requests.get(
                    api_url,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code != 200:
                    raise UserError(_(f"Failed to fetch lines from API: {response.text} (Status: {response.status_code})"))

                lines = response.json()
                _logger.info("API returned %s lines", len(lines))
                
                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.line.last_sync', current_time)

                synced_count = 0
                skipped_count = 0
                api_line_ids = set()

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
                                            'line_id': False,
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

                        api_data_serialized = self._serialize_line_data(
                            line,
                            departure_station.id if departure_station else False,
                            terminus_station.id if departure_station else False,
                            line_station_ids
                        )

                        api_line_ids.add(external_id)

                        existing_line = existing_line_map.get(external_id)
                        if existing_line:
                            existing_data_serialized = self._serialize_existing_line(existing_line)
                            if existing_data_serialized == api_data_serialized:
                                _logger.debug(f"Skipping line with external_id {external_id}: No changes")
                                skipped_count += 1
                                continue

                            existing_line.with_context(from_sync=True).write(line_data)
                            existing_line.line_station_ids.unlink()
                            for ls_id in line_station_ids:
                                self.env['infrastructure.line.station'].browse(ls_id).write({'line_id': existing_line.id})
                            _logger.info(f"Updated line with external_id {external_id}")
                            synced_count += 1
                        else:
                            new_line = self.with_context(from_sync=True).create(line_data)
                            for ls_id in line_station_ids:
                                self.env['infrastructure.line.station'].browse(ls_id).write({'line_id': new_line.id})
                            _logger.info(f"Created line with external_id {external_id}")
                            synced_count += 1

                    except Exception as e:
                        _logger.error(f"Failed to process line {line.get('id', 'Unknown')}: {str(e)}")
                        skipped_count += 1

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

                result['lines'] = {'synced': synced_count, 'skipped': skipped_count}
                result['messages'].append(f"Lines sync completed: {synced_count} synced, {skipped_count} skipped")

            return result

        except requests.RequestException as e:
            error_message = f"Line sync failed: {str(e)}"
            _logger.error(error_message)
            raise UserError(_(error_message))

    @api.model
    def _serialize_line_data(self, line_data, departure_id, terminus_id, line_station_ids):
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