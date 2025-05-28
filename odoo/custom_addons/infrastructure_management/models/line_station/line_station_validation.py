from odoo import models, api, _
from odoo.exceptions import ValidationError

class InfrastructureLineStation(models.Model):
    _inherit = 'infrastructure.line.station'

    @api.constrains('lat', 'lng')
    def _check_coordinates(self):
        for record in self:
            if record.lat and (record.lat < -90 or record.lat > 90):
                raise ValidationError(_("Latitude must be between -90 and 90 degrees."))
            if record.lng and (record.lng < -180 or record.lng > 180):
                raise ValidationError(_("Longitude must be between -180 and 180 degrees."))

    @api.constrains('order', 'line_id', 'direction')
    def _check_unique_order(self):
        for record in self:
            duplicates = self.search([
                ('line_id', '=', record.line_id.id),
                ('direction', '=', record.direction),
                ('order', '=', record.order),
                ('id', '!=', record.id)
            ])
            if duplicates:
                raise ValidationError(_(
                    f"Order {record.order} is already used for line {record.line_id.enterprise_code} "
                    f"in direction {record.direction}."
                ))