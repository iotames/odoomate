import os
import zlib
from odoo import models, fields, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StcGitInfo(models.Model):
    _name = 'stc.git.info'
    _description = 'Git Version Tracker'
    # 40个字符的哈希值
    commit_hash = fields.Char('Commit ID', size=64)
    commit_message = fields.Text('Message')
    commit_data = fields.Text('Commit Data')
    commit_date = fields.Datetime('Date')
    branch_name = fields.Char('Branch')
    release_tag = fields.Char('Release Tag')

    def _get_git_dir(self):
        return self.env['ir.config_parameter'].sudo().get_param('git_info.git_dir', default='/mnt/extra-addons/.git')

    def _get_timezone(self):
        return self.env['ir.config_parameter'].sudo().get_param('git_info.timezone', default='+0800')

    def _parse_git_object(self, git_dir, obj_hash):
        """解析Git对象文件"""
        _logger.info("-----_parse_git_object---commit_hash(%s)", obj_hash)
        try:
            obj_path = os.path.join(git_dir, 'objects', obj_hash[:2], obj_hash[2:])
            with open(obj_path, 'rb') as f:
                raw_data = zlib.decompress(f.read())
                return raw_data.split(b'\x00', 1)[1].decode('utf-8', 'ignore')
        except Exception as e:
            raise UserError(_("Git解析错误: %s") % str(e))

    def _get_commit_info(self, git_dir):
        """获取最新提交信息"""
        try:
            # 解析HEAD文件
            head_path = os.path.join(git_dir, 'HEAD')
            with open(head_path, 'r') as f:
                ref = f.read().strip()
                
            if ref.startswith('ref: '):
                branch_path = ref[5:]
                ref_path = os.path.join(git_dir, branch_path)
                with open(ref_path, 'r') as f:
                    commit_hash = f.read().strip()
                branch = branch_path.split('/')[-1]
            else:
                commit_hash = ref
                branch = 'detached'
                
            # 解析commit对象
            commit_data = self._parse_git_object(git_dir, commit_hash)
            message = commit_data.split('\n\n', 1)[1].split('\n')[0]
            # 提取时间戳和时区信息
            author_line = next(line for line in commit_data.split('\n') if line.startswith('author'))
            parts = author_line.split(' ')
            date_str = parts[-2]  # 时间戳
            timezone = self._get_timezone()
            if timezone == '':
                timezone = parts[-1]  # 时区偏移，如 +0800
            print("------timezone-----------:", timezone)
            # 修复日期处理部分
            try:
                # 尝试直接转换Unix时间戳
                import datetime
                timestamp = int(date_str)
                # 解析时区偏移（单位：秒），格式如 "+0800"
                tz_sign = -1 if timezone.startswith('-') else 1
                tz_hours = int(timezone[1:3])
                tz_minutes = int(timezone[3:5])  # 注意这里是 3:5，不是 3:

                tz_offset = tz_sign * (tz_hours * 3600 + tz_minutes * 60)
                print("------tz_sign({})---tz_hours({})---tz_minutes({})--tz_offset({})---".format(tz_sign, tz_hours, tz_minutes, tz_offset))
                try:
                    # 确保时间戳在合理范围内
                    if timestamp < 0 or timestamp > 2147483647:  # 2147483647 是 Unix 时间戳上限
                        _logger.warning("无法将 %s 解析为时间戳，使用当前时间", date_str)
                        raise UserError(_("{}超过unix时间戳范围0~2147483647".format(date_str)))  
                    # 创建时区对象
                    from datetime import timezone, timedelta
                    tz = timezone(timedelta(seconds=tz_offset))
                    
                    # 创建带有时区的datetime对象
                    local_dt = datetime.datetime.fromtimestamp(timestamp, tz)                    
                    # 转换为 Odoo 上下文时区
                    # formatted_date = fields.Datetime.to_string(
                    #     fields.Datetime.context_timestamp(self, local_dt)
                    # )
                except (ValueError, OverflowError) as e:
                    _logger.warning("无法将 %s 解析为有效时间戳，错误：%s，使用当前时间", timestamp, str(e))
                    raise UserError(_("解析时间戳错误"))
                print("-----local_dt({})----".format(local_dt))
            except ValueError:
                # 如果不是时间戳，则使用安全的方式处理日期字符串
                _logger.warning("无法将 %s 解析为时间戳，使用当前时间", date_str)
                raise UserError(_("解析时间戳错误"))
                # formatted_date = fields.Datetime.to_string(
                #     fields.Datetime.context_timestamp(self, fields.Datetime.now()))
            return {
                'hash': commit_hash,
                'message': message,
                'data': commit_data,
                'date': fields.Datetime.to_string(local_dt),
                # 'date': formatted_date,
                'branch': branch
            }
        except FileNotFoundError:
            raise UserError(_("未找到Git仓库配置"))

    def _get_latest_tag(self, git_dir):
        """获取最新标签"""
        tags_dir = os.path.join(git_dir, 'refs', 'tags')
        if os.path.exists(tags_dir):
            tags = [f for f in os.listdir(tags_dir) 
                   if os.path.isfile(os.path.join(tags_dir, f))]
            return max(tags) if tags else ''
        return ''

    def refresh_git_info(self):
        """刷新版本信息"""
        # git_dir = "/mnt/extra-addons/.git"
        git_dir = self.env['ir.config_parameter'].sudo().get_param('git_info.git_dir')
        # 如果git_dir为False或None，设置默认值
        if not git_dir:
            git_dir = "/mnt/extra-addons/.git"
        if not isinstance(git_dir, str):
            raise UserError(_("git_dir 必须是字符串类型"))
        if not os.path.exists(git_dir):
            _logger.warning(_("Git目录 %s 不存在"), git_dir)
            raise UserError(_("Git目录 %s 不存在") % git_dir)
        _logger.info("-----refresh_git_info--找到--Git目录: %s", git_dir)
        # self.search([]).unlink()  # 清理旧记录
        
        commit_info = self._get_commit_info(git_dir)
        release_tag = self._get_latest_tag(git_dir)
        
        # 查询最近一条记录
        latest_record = self.search([], order='commit_date desc', limit=1)
        
        # 如果存在记录且hash值相同，则跳过创建
        if latest_record and latest_record.commit_hash == commit_info['hash']:
            _logger.info("检测到相同的commit hash，跳过创建新记录")
            # self.env.user.notify_success(message='已是最新了')
            raise UserError(_("已是最新了"))
            
        # 创建新记录
        self.create({
            'commit_hash': commit_info['hash'],
            'commit_message': commit_info['message'],
            'commit_data': commit_info['data'],
            'commit_date': commit_info['date'],
            'branch_name': commit_info['branch'],
            'release_tag': release_tag
        })

    # 使用交互式命令进行调试
    # python odoo\odoo-bin shell -c odoo.conf
    # env = self.env['stc.git.info']
    # records = env.search([('field', '=', value)])  # 查询记录
    # self.env['stc.git.info'].debug()
    def debug(self):
        print("Hello git_dir={}, timezone={}".format(self._get_git_dir(), self._get_timezone()))
