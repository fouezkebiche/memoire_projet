from odoo import models, fields

class TestItem(models.Model):
    _name = "test.item"
    _description = "Test Item"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
