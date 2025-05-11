# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class stc_git_info(models.Model):
#     _name = 'stc_git_info.stc_git_info'
#     _description = 'stc_git_info.stc_git_info'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

