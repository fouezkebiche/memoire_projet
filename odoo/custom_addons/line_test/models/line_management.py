# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError
import requests
import logging
import time

_logger = logging.getLogger(__name__)

class LineManagement(models.Model):
    _name = 'line.management'
    _description = 'Transport Line'
    _rec_name = 'code'
    _order = 'code asc'

    # Basic Information
    api_id = fields.Integer(string='API ID', index=True, readonly=True, help="ID from the external API")
    code = fields.Char(string='Line Code', required=True, index=True)
    color = fields.Char(string='Color')
    enterprise_code = fields.Char(string='Enterprise Code')
    line_type = fields.Selection(
        [('1', 'Type 1'), ('2', 'Type 2')],
        string='Line Type'
    )
    active = fields.Boolean(string='Active', default=True)

    # Departure Station Information
    departure_station = fields.Char(string='Departure Station (EN)')
    departure_station_ar = fields.Char(string='Departure Station (AR)')
    departure_station_fr = fields.Char(string='Departure Station (FR)')
    departure_lat = fields.Float(string='Departure Latitude', digits=(10, 7))
    departure_lng = fields.Float(string='Departure Longitude', digits=(10, 7))

    # Terminus Station Information
    terminus_station = fields.Char(string='Terminus Station (EN)')
    terminus_station_ar = fields.Char(string='Terminus Station (AR)')
    terminus_station_fr = fields.Char(string='Terminus Station (FR)')
    terminus_lat = fields.Float(string='Terminus Latitude', digits=(10, 7))
    terminus_lng = fields.Float(string='Terminus Longitude', digits=(10, 7))

    # Schedule Information
    schedule = fields.Text(string='Schedule Summary')
    schedule_ids = fields.One2many(
        'line.schedule', 'line_id', string='Detailed Schedule',
        help="Detailed departure times for this line"
    )

    def _prepare_api_data(self):
        """ Prepare data for API create/update """
        self.ensure_one()
        departure = {
            'nameEn': self.departure_station,
            'nameAr': self.departure_station_ar,
            'nameFr': self.departure_station_fr,
            'lat': self.departure_lat,
            'lng': self.departure_lng,
        }
        terminus = {
            'nameEn': self.terminus_station,
            'nameAr': self.terminus_station_ar,
            'nameFr': self.terminus_station_fr,
            'lat': self.terminus_lat,
            'lng': self.terminus_lng,
        }
        schedule_times = [s.time for s in self.schedule_ids if s.time]
        
        return {
            'code': self.code,
            'color': self.color or '',
            'enterpriseCode': self.enterprise_code or '',
            'lineType': int(self.line_type) if self.line_type else None,
            'departureStation': departure,
            'terminusStation': terminus,
            'schedule': schedule_times,
            'lineStations': [],  # Add logic for line stations if needed
        }

    def _make_api_request(self, method, url, data=None, retries=3, timeout=15):
        """ Helper method to make API requests with retries """
        for attempt in range(retries):
            try:
                if method == 'GET':
                    response = requests.get(url, timeout=timeout)
                elif method == 'POST':
                    response = requests.post(url, json=data, timeout=timeout)
                elif method == 'PUT':
                    response = requests.put(url, json=data, timeout=timeout)
                elif method == 'DELETE':
                    response = requests.delete(url, timeout=timeout)
                else:
                    raise ValueError("Unsupported HTTP method")
                
                response.raise_for_status()
                return response
            except requests.exceptions.ConnectTimeout as e:
                _logger.warning("API request timed out (attempt %s/%s): %s", attempt + 1, retries, e)
                if attempt == retries - 1:
                    raise UserError("Cannot connect to the API server. Please check your network or try again later.")
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    raise UserError("Resource not found in the API.")
                raise UserError(f"API error: {e}")
            except requests.exceptions.RequestException as e:
                _logger.warning("API request failed (attempt %s/%s): %s", attempt + 1, retries, e)
                if attempt == retries - 1:
                    raise UserError(f"Failed to communicate with the API: {e}")
                time.sleep(2 ** attempt)
        return None

    @api.model
    def create_line_in_api(self, vals):
        """ Create a new line in the external API """
        url = "http://147.93.52.105:8082/infra/line"
        try:
            # Prepare API data from vals
            departure = {
                'nameEn': vals.get('departure_station'),
                'nameAr': vals.get('departure_station_ar'),
                'nameFr': vals.get('departure_station_fr'),
                'lat': vals.get('departure_lat'),
                'lng': vals.get('departure_lng'),
            }
            terminus = {
                'nameEn': vals.get('terminus_station'),
                'nameAr': vals.get('terminus_station_ar'),
                'nameFr': vals.get('terminus_station_fr'),
                'lat': vals.get('terminus_lat'),
                'lng': vals.get('terminus_lng'),
            }
            schedule_times = vals.get('schedule', '').split(', ') if vals.get('schedule') else []
            api_data = {
                'code': vals.get('code'),
                'color': vals.get('color', ''),
                'enterpriseCode': vals.get('enterprise_code', ''),
                'lineType': int(vals.get('line_type')) if vals.get('line_type') else None,
                'departureStation': departure,
                'terminusStation': terminus,
                'schedule': schedule_times,
                'lineStations': [],  # Add logic for line stations if needed
            }

            response = self._make_api_request('POST', url, data=api_data)
            api_id = response.json().get('id') if response.json() else None
            _logger.info("Created line in API: %s", api_data.get('code'))
            return api_id
        except UserError as e:
            raise
        except Exception as e:
            _logger.error("Failed to create line in API: %s", e)
            raise UserError(f"Failed to create line in API: {e}")

    def update_line_in_api(self):
        """ Update an existing line in the external API """
        self.ensure_one()
        if not self.api_id:
            raise UserError("Cannot update line: API ID is missing.")
        
        url = f"http://147.93.52.105:8082/infra/line/{self.api_id}"
        try:
            api_data = self._prepare_api_data()
            self._make_api_request('PUT', url, data=api_data)
            _logger.info("Updated line in API: %s", self.code)
        except UserError as e:
            raise
        except Exception as e:
            _logger.error("Failed to update line in API: %s", e)
            raise UserError(f"Failed to update line in API: {e}")

    def delete_line_in_api(self):
        """ Delete a line in the external API """
        self.ensure_one()
        if not self.api_id:
            raise UserError("Cannot delete line: API ID is missing.")
        
        url = f"http://147.93.52.105:8082/infra/line/{self.api_id}"
        try:
            self._make_api_request('DELETE', url)
            _logger.info("Deleted line in API: %s", self.code)
        except UserError as e:
            raise
        except Exception as e:
            _logger.error("Failed to delete line in API: %s", e)
            raise UserError(f"Failed to delete line in API: {e}")

    @api.model
    def sync_lines_from_api(self):
        """ Synchronize transport lines from external API """
        if self.env.context.get('skip_sync'):
            _logger.info("Skipping API sync due to context")
            return {'type': 'ir.actions.act_window_close'}

        url = "http://147.93.52.105:8082/infra/line"
        try:
            response = self._make_api_request('GET', url)
            lines = response.json()

            existing_lines = self.search([])
            existing_api_ids = existing_lines.mapped('api_id')
            api_ids = [line.get('id') for line in lines]

            # Deactivate lines not in API
            lines_to_deactivate = existing_lines.filtered(
                lambda l: l.api_id not in api_ids
            )
            lines_to_deactivate.write({'active': False})

            for line in lines:
                departure = line.get('departureStation', {})
                terminus = line.get('terminusStation', {})
                
                # Prepare schedule data
                schedule_times = line.get('schedule', [])
                schedule_vals = [(5, 0, 0)]  # Clear existing schedules
                for time in schedule_times:
                    schedule_vals.append((0, 0, {
                        'time': time,
                        'direction': 'GOING'
                    }))
                
                vals = {
                    'api_id': line.get('id'),
                    'code': line.get('code'),
                    'color': line.get('color'),
                    'enterprise_code': line.get('enterpriseCode'),
                    'line_type': str(line.get('lineType')),
                    'departure_station': departure.get('nameEn'),
                    'departure_station_ar': departure.get('nameAr'),
                    'departure_station_fr': departure.get('nameFr'),
                    'departure_lat': departure.get('lat'),
                    'departure_lng': departure.get('lng'),
                    'terminus_station': terminus.get('nameEn'),
                    'terminus_station_ar': terminus.get('nameAr'),
                    'terminus_station_fr': terminus.get('nameFr'),
                    'terminus_lat': terminus.get('lat'),
                    'terminus_lng': terminus.get('lng'),
                    'schedule': ", ".join(schedule_times),
                    'schedule_ids': schedule_vals,
                    'active': True,
                }

                # Update or create record
                existing_line = self.search([('api_id', '=', line.get('id'))], limit=1)
                if existing_line:
                    existing_line.write(vals)
                else:
                    self.with_context(skip_sync=True).create(vals)

            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Lines synchronized successfully!',
                    'type': 'rainbow_man',
                }
            }

        except UserError as e:
            raise
        except Exception as e:
            _logger.error("Failed to sync lines from API: %s", e)
            raise UserError(f"Failed to sync lines from API: {e}")

    @api.model
    def create(self, vals):
        """ Override create to sync with API """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Only managers can create lines.")
        
        api_id = self.create_line_in_api(vals)
        if api_id:
            vals['api_id'] = api_id
        record = super(LineManagement, self).create(vals)
        try:
            self.with_context(skip_sync=True).sync_lines_from_api()
        except UserError as e:
            _logger.warning("Post-create sync failed: %s", e)
        return record

    def write(self, vals):
        """ Override write to sync with API """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Only managers can update lines.")
        
        for record in self:
            if record.api_id:
                record.update_line_in_api()
        result = super(LineManagement, self).write(vals)
        try:
            self.with_context(skip_sync=True).sync_lines_from_api()
        except UserError as e:
            _logger.warning("Post-update sync failed: %s", e)
        return result

    def unlink(self):
        """ Override unlink to sync with API """
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Only managers can delete lines.")
        
        for record in self:
            if record.api_id:
                record.delete_line_in_api()
        result = super(LineManagement, self).unlink()
        try:
            self.env['line.management'].with_context(skip_sync=True).sync_lines_from_api()
        except UserError as e:
            _logger.warning("Post-delete sync failed: %s", e)
        return result