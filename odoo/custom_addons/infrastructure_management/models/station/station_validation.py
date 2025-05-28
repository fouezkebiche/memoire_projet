from odoo import models, api, _
from odoo.exceptions import ValidationError
import json

class InfrastructureStation(models.Model):
    _inherit = 'infrastructure.station'

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError(_("Latitude must be between -90 and 90 degrees."))
            if record.longitude and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError(_("Longitude must be between -180 and 180 degrees."))

    @api.constrains('paths', 'changes', 'schedule')
    def _check_json_fields(self):
        for record in self:
            for field in ['paths', 'changes', 'schedule']:
                if record[field]:
                    try:
                        json.loads(record[field])
                    except json.JSONDecodeError:
                        raise ValidationError(_("%s must be a valid JSON string.") % field.capitalize())

    @api.model
    def _serialize_station_data(self, station_data, line_ids):
        data = {
            'name_ar': station_data.get('nameAr', ''),
            'name_en': station_data.get('nameEn', ''),
            'name_fr': station_data.get('nameFr', ''),
            'latitude': float(station_data.get('lat', 0.0)),
            'longitude': float(station_data.get('lng', 0.0)),
            'paths': station_data.get('paths', []) or [],
            'changes': station_data.get('changes', {}) or {},
            'schedule': station_data.get('schedule', []) or [],
            'line_ids': sorted(line_ids)
        }
        return json.dumps(data, sort_keys=True)

    @api.model
    def _serialize_existing_station(self, station):
        data = {
            'name_ar': station.name_ar,
            'name_en': station.name_en,
            'name_fr': station.name_fr,
            'latitude': station.latitude,
            'longitude': station.longitude,
            'paths': json.loads(station.paths) if station.paths else [],
            'changes': json.loads(station.changes) if station.changes else {},
            'schedule': json.loads(station.schedule) if station.schedule else [],
            'line_ids': sorted(station.line_ids.ids)
        }
        return json.dumps(data, sort_keys=True)