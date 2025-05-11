# -*- coding: utf-8 -*-
# from odoo import http


# class StcGitInfo(http.Controller):
#     @http.route('/stc_git_info/stc_git_info', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stc_git_info/stc_git_info/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('stc_git_info.listing', {
#             'root': '/stc_git_info/stc_git_info',
#             'objects': http.request.env['stc_git_info.stc_git_info'].search([]),
#         })

#     @http.route('/stc_git_info/stc_git_info/objects/<model("stc_git_info.stc_git_info"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stc_git_info.object', {
#             'object': obj
#         })

