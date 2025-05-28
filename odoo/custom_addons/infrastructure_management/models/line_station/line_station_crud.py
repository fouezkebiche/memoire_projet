from odoo import models, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)

class InfrastructureLineStation(models.Model):
    _inherit = 'infrastructure.line.station'

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
                raise UserError(_(
                    f"Order {order} is already used for line {existing.line_id.enterprise_code} "
                    f"in direction {direction}."
                ))

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
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries))
            response = session.post(
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
                            raise UserError(_(f"Failed to parse external_id from response: {response_text}"))
                    else:
                        raise UserError(_(f"Unexpected API response format: {response_text}"))
                
                self._cr.execute('UPDATE infrastructure_line_station SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to line station %s", external_id, record.id)
            else:
                raise UserError(_(f"Failed to create line station in API: {response.text} (Status: {response.status_code})"))
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(_(f"API request failed: {str(e)}"))

        return record

    def write(self, vals):
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
                session = requests.Session()
                retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
                session.mount('http://', HTTPAdapter(max_retries=retries))
                response = session.put(
                    api_url,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    data=payload,
                    timeout=10
                )
                _logger.info("API PUT %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                if response.status_code not in (200, 201, 204):
                    raise UserError(_(f"Failed to update line station in API: {response.text} (Status: {response.status_code})"))
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(_(f"API request failed: {str(e)}"))

        return result

    def unlink(self):
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for line station during sync: %s", self.ids)
            return super(InfrastructureLineStation, self).unlink()

        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:9000/infra/linestation/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s for line station %s (external_id: %s)",
                                 api_url, record.id, record.external_id)
                    session = requests.Session()
                    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
                    session.mount('http://', HTTPAdapter(max_retries=retries))
                    response = session.delete(
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
                    _logger.error("API DELETE request failed for line station %s (external_id: %s): %s",
                                  record.id, record.external_id, str(e))
                    # Proceed with Odoo deletion despite API failure
            else:
                _logger.info("Skipping API delete for line station %s: No external_id.", record.id)

        return super(InfrastructureLineStation, self).unlink()