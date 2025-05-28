from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import requests
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)

class InfrastructureStation(models.Model):
    _inherit = 'infrastructure.station'

    @api.model
    def sync_infrastructure(self, sync_stations=False, sync_lines=False, sync_line_stations=False):
        result = {
            'stations': {'synced': 0, 'skipped': 0},
            'lines': {'synced': 0, 'skipped': 0},
            'line_stations': {'synced': 0, 'skipped': 0},
            'messages': []
        }

        if not any([sync_stations, sync_lines, sync_line_stations]):
            raise UserError(_("Please select at least one entity to sync (Stations, Lines, or Line Stations)"))

        try:
            if sync_stations:
                api_url = 'http://147.93.52.105:9000/infra/station'
                _logger.info("Fetching all stations from API: %s", api_url)
                response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=30)
                if response.status_code != 200:
                    raise UserError(_(f"Failed to fetch stations from API: {response.text} (Status: {response.status_code})"))

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

                current_time = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                self.env['ir.config_parameter'].sudo().set_param('infrastructure.station.last_sync', current_time)

            return result

        except Exception as e:
            _logger.error("Infrastructure sync failed: %s", str(e))
            raise UserError(_(f"Infrastructure sync failed: {str(e)}"))