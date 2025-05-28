from odoo import models, api, _
from odoo.exceptions import ValidationError
import json

class InfrastructureLine(models.Model):
    _inherit = 'infrastructure.line'

    @api.constrains('schedule')
    def _check_schedule(self):
        for record in self:
            if record.schedule:
                try:
                    json.loads(record.schedule)
                except json.JSONDecodeError:
                    raise ValidationError(_("%s must be a valid JSON string.") % "Schedule")