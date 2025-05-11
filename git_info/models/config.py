from odoo import models, fields, api

class GitInfoConfig(models.TransientModel):
    _name = 'git.info.config'
    _inherit = 'res.config.settings'
    _description = 'Git信息配置'

    # 定义字段
    git_dir = fields.Char(
        string=".git目录",
        default="/mnt/extra-addons/.git",
        config_parameter="git_info.git_dir"
    )
    
    timezone = fields.Selection(
        [('', '无'), ('+0000', 'UTC'), ('+0800', '北京时间')],
        string="时区",
        default='+0800',
        config_parameter="git_info.timezone"
    )
    
    @api.model
    def get_values(self):
        res = super(GitInfoConfig, self).get_values()
        res.update(
            git_dir=self.env['ir.config_parameter'].sudo().get_param('git_info.git_dir', default='/mnt/extra-addons/.git'),
            timezone=self.env['ir.config_parameter'].sudo().get_param('git_info.timezone', default='+0800'),
        )
        return res
        
    def set_values(self):
        super(GitInfoConfig, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('git_info.git_dir', self.git_dir or '/mnt/extra-addons/.git')
        self.env['ir.config_parameter'].sudo().set_param('git_info.timezone', self.timezone or '+0800')
        self.env.cr.commit()  # 强制提交事务