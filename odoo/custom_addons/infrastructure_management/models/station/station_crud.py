from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class InfrastructureStation(models.Model):
    _inherit = 'infrastructure.station'

    @api.model
    def create(self, vals):
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(_("%s must be a valid JSON string.") % field.capitalize())

        if self._context.get('from_sync'):
            _logger.info("Creating station in Odoo from sync: %s (external_id: %s)", vals.get('name_en'), vals.get('external_id'))
            return super(InfrastructureStation, self).create(vals)

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
                            raise UserError(_(f"Failed to parse external_id from API response: {response_text}"))
                    else:
                        _logger.error("Unexpected response format: %s", response_text)
                        raise UserError(_(f"Unexpected API response format: {response_text}"))
                
                self._cr.execute('UPDATE infrastructure_station SET external_id = %s WHERE id = %s', (external_id, record.id))
                _logger.info("Assigned external_id %s to station %s", external_id, record.name_en)
            else:
                raise UserError(_(f"Failed to create station in API: {response.text} (Status: {response.status_code})"))
        except requests.RequestException as e:
            _logger.error("API POST request failed: %s", str(e))
            raise UserError(_(f"API request failed: {str(e)}"))

        return record

    def write(self, vals):
        for field in ['paths', 'changes', 'schedule']:
            if vals.get(field):
                try:
                    json.loads(vals[field])
                except json.JSONDecodeError:
                    raise UserError(_("%s must be a valid JSON string.") % field.capitalize())

        if self._context.get('from_sync'):
            _logger.info("Skipping API update for station during sync: %s", self.name_en)
            return super(InfrastructureStation, self).write(vals)

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
                    raise UserError(_(f"Failed to update station in API: {response.text} (Status: {response.status_code})"))
            except requests.RequestException as e:
                _logger.error("API PUT request failed: %s", str(e))
                raise UserError(_(f"API request failed: {str(e)}"))

        return result

    def unlink(self):
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for station during sync: %s", self.name_en)
            return super(InfrastructureStation, self).unlink()

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