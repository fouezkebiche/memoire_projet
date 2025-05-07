from odoo import models, fields

class InfrastructureLineType(models.Model):
    _name = 'infrastructure.line.type'
    _description = 'Infrastructure Line Type'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)

    def name_get(self):
        """Display name in dropdowns, with code as fallback."""
        result = []
        for line_type in self:
            name = line_type.name or line_type.code or 'Unnamed Type'
            result.append((line_type.id, name))
        return result