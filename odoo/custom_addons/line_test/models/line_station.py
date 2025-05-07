# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class LineStation(models.Model):
    _name = 'line.station'
    _description = 'Line Station Details'
    _order = 'order asc'

    line_id = fields.Many2one('line.management', string='Line', required=True, ondelete='cascade')
    order = fields.Integer(string='Order', required=True)
    stop_duration = fields.Integer(string='Stop Duration (seconds)')
    direction = fields.Selection(
        [('GOING', 'Going'), ('RETURNING', 'Returning')],
        string='Direction',
        default='GOING',
        required=True
    )
    station_name_en = fields.Char(string='Station Name (EN)')
    station_name_ar = fields.Char(string='Station Name (AR)')
    station_name_fr = fields.Char(string='Station Name (FR)')
    lat = fields.Float(string='Latitude', digits=(10, 7))
    lng = fields.Float(string='Longitude', digits=(10, 7))
    radius = fields.Integer(string='Radius (meters)')
    alertable = fields.Boolean(string='Alertable')
    efficient = fields.Boolean(string='Efficient')
    duration = fields.Integer(string='Duration (minutes)')
    api_id = fields.Integer(string='API ID', index=True, help="ID from the external API")

    @api.model
    def sync_line_stations_from_api(self):
        """ Synchronize line stations from external API by iterating over IDs """
        base_url = "http://147.93.52.105:8082/infra/linestation/"
        max_id = 50  # Reduced for testing; increase as needed
        try:
            existing_stations = self.search([])
            existing_api_ids = existing_stations.mapped('api_id')
            fetched_stations = []

            _logger.info("Starting line station sync from API: %s", base_url)
            # Fetch data for each ID
            for station_id in range(1, max_id + 1):
                try:
                    _logger.debug("Fetching station ID %s", station_id)
                    response = requests.get(f"{base_url}{station_id}", timeout=5)
                    _logger.debug("Response status for ID %s: %s", station_id, response.status_code)
                    
                    if response.status_code == 200:
                        try:
                            station_data = response.json()
                            _logger.debug("Station data for ID %s: %s", station_id, station_data)
                            fetched_stations.append(station_data)
                        except ValueError:
                            _logger.warning("Invalid JSON response for station ID %s", station_id)
                            continue
                    else:
                        _logger.info("No station found for ID %s (Status: %s)", station_id, response.status_code)
                except requests.exceptions.RequestException as e:
                    _logger.warning("Failed to fetch station ID %s: %s", station_id, e)
                    continue

            _logger.info("Fetched %s stations from API", len(fetched_stations))
            # Process fetched stations
            for station in fetched_stations:
                line_data = station.get('line', {})
                station_data = station.get('station', {})
                
                # Validate required data
                if not line_data or not station_data:
                    _logger.warning("Missing line or station data for station ID %s", station.get('id'))
                    continue

                # Find the corresponding line
                line_code = line_data.get('code')
                line = self.env['line.management'].search([('code', '=', line_code)], limit=1)
                if not line:
                    _logger.warning("Line with code %s not found for station ID %s", line_code, station.get('id'))
                    continue

                vals = {
                    'api_id': station.get('id'),
                    'line_id': line.id,
                    'order': station.get('order'),
                    'stop_duration': station.get('stopDuration'),
                    'direction': station.get('direction'),
                    'station_name_en': station_data.get('nameEn'),
                    'station_name_ar': station_data.get('nameAr'),
                    'station_name_fr': station_data.get('nameFr'),
                    'lat': station.get('lat'),
                    'lng': station.get('lng'),
                    'radius': station.get('radius'),
                    'alertable': station.get('alertable'),
                    'efficient': station.get('efficient'),
                    'duration': station.get('duration'),
                }

                # Update or create record
                existing_station = self.search([('api_id', '=', station.get('id'))], limit=1)
                if existing_station:
                    _logger.debug("Updating station ID %s", station.get('id'))
                    existing_station.write(vals)
                else:
                    _logger.debug("Creating station ID %s", station.get('id'))
                    self.create(vals)

            # Deactivate stations not in fetched data
            fetched_api_ids = [station.get('id') for station in fetched_stations]
            stations_to_deactivate = existing_stations.filtered(
                lambda s: s.api_id not in fetched_api_ids
            )
            if stations_to_deactivate:
                _logger.info("Deactivating %s stations not in API", len(stations_to_deactivate))
                stations_to_deactivate.unlink()  # Or set active=False if preferred

            _logger.info("Line station sync completed successfully")
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Line stations synchronized successfully!',
                    'type': 'rainbow_man',
                }
            }

        except Exception as e:
            _logger.error("Unexpected error during line station sync: %s", e)
            raise UserError(f"Unexpected error during sync: {e}")