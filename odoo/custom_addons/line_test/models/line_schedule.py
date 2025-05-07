# -*- coding: utf-8 -*-

from odoo import models, fields, api

class LineSchedule(models.Model):
    _name = 'line.schedule'
    _description = 'Line Schedule Details'
    _order = 'time asc'

    line_id = fields.Many2one('line.management', string='Line', ondelete='cascade')
    time = fields.Char(string='Departure Time', required=True)
    direction = fields.Selection(
        [('GOING', 'Going'), ('RETURN', 'Return')],
        string='Direction',
        default='GOING',
        required=True
    )