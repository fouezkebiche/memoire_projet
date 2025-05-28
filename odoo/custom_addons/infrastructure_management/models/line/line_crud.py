from odoo import models, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class InfrastructureLine(models.Model):
    _inherit = 'infrastructure.line'

    @api.model
    def create(self, vals):
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError(_("%s must be a valid JSON string.") % "Schedule")

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
                            raise UserError(_(f"Failed to parse external_id from response: {response_text}"))
                    else:
                        raise UserError(_(f"Unexpected API response format: {response_text}"))
                
                self._cr.execute('UPDATE infrastructure_line SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to line %s", external_id, record.enterprise_code)
            else:
                raise UserError(_(f"Failed to create line in API: {response.text} (Status: {response.status_code})"))
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(_(f"API request failed: {str(e)}"))

        return record

    def write(self, vals):
        if vals.get('schedule'):
            try:
                json.loads(vals['schedule'])
            except json.JSONDecodeError:
                raise UserError(_("%s must be a valid JSON string.") % "Schedule")

        result = super(InfrastructureLine, self).write(vals)

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
                    raise UserError(_(f"Failed to update line in API: {response.text} (Status: {response.status_code})"))
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(_(f"API request failed: {str(e)}"))

        return result

    def unlink(self):
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