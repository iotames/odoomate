import os
import zlib
import re
from datetime import timezone, timedelta, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StcGitInfo(models.Model):
    _name = 'stc.git.info'
    _description = 'Git Version Tracker'
    # 40个字符的哈希值
    commit_hash = fields.Char('Commit Hash', size=64)
    commit_title = fields.Text('Commit Title', compute='_compute_commit_title')
    commit_data = fields.Text('Commit Data')
    # commit_date = fields.Datetime('Date')
    commit_date = fields.Datetime('Date', compute='_compute_commit_date', store=True)
    commit_desc = fields.Text('Description', compute='_compute_commit_desc')
    branch_name = fields.Char('Branch')
    release_tag = fields.Char('Release Tag')

    @api.depends('commit_data')
    def _compute_commit_date(self):
        for record in self:
            if record.commit_data:
                record.commit_date = self._get_date_from_commit_data(record.commit_data, with_timezone=False)
                print("----_compute_commit_date----commit_date({})---".format(record.commit_date))
            else:
                record.commit_date = False

    @api.depends('commit_data')
    def _compute_commit_desc(self):
        for record in self:
            if record.commit_data:
                record.commit_desc = self._get_commit_desc_from_commit_data(record.commit_data)
            else:
                record.commit_desc = False

    def _get_commit_desc_from_commit_data(self, commit_data):
        # 从commit数据中提取第三段内容的第一行
        parts = commit_data.split('\n\n')
        if len(parts) >= 3:
            lines = parts[2].split('\n')
            if lines:
                return lines[0]
        return ''

    @api.depends('commit_data')
    def _compute_commit_title(self):
        for record in self:
            if record.commit_data:
                record.commit_title = self._get_commit_title_from_commit_data(record.commit_data)
            else:
                record.commit_title = False

    def _get_commit_title_from_commit_data(self, commit_data):
        # 从commit数据中提取第三段内容的第一行
        parts = commit_data.split('\n\n')
        if len(parts) >= 2:
            lines = parts[1].split('\n')
            if lines:
                return lines[0]
        return ''

    def _get_git_dir(self):
        return self.env['ir.config_parameter'].sudo().get_param('git_info.git_dir', default='/mnt/extra-addons/.git')
    
    def _check_git_dir(self, git_dir):
        if not isinstance(git_dir, str):
            raise UserError(_("git_dir 必须是字符串类型"))
        if not os.path.exists(git_dir):
            err_msg = f"Git目录 {git_dir} 不存在。请新建或修改配置：设置-技术-参数-系统参数: git_info.git_dir"
            _logger.warning(_(err_msg))
            raise UserError(err_msg)

    def _get_time_info_from_commit_data(self, commit_data):
        # 提取时间戳和时区信息
        author_line = next(line for line in commit_data.split('\n') if line.startswith('author'))
        parts = author_line.split(' ')
        date_str = parts[-2]  # 时间戳
        timezonestr = parts[-1]  # 时区信息
        print("------date_str({})---timezonestr({})---".format(date_str, timezonestr))
        return {
            'date_str': date_str,
            'timezonestr': timezonestr
        }

    def _get_timezone(self, commit_data=""):
        tzstr = self.env['ir.config_parameter'].sudo().get_param('git_info.timezone', default='+0800')
        if tzstr == "":
            tzstr = self._get_time_info_from_commit_data(commit_data)['timezonestr']
        if tzstr == "":
            tzstr = "+0800"
        print("------timezone----tzstr-------:", tzstr) # 时区偏移，如 +0800
        # 解析时区偏移（单位：秒），格式如 "+0800"
        tz_sign = -1 if tzstr.startswith('-') else 1
        tz_hours = int(tzstr[1:3])
        tz_minutes = int(tzstr[3:5])  # 注意这里是 3:5，不是 3:
        tz_offset = tz_sign * (tz_hours * 3600 + tz_minutes * 60)
        print("------tz_sign({})---tz_hours({})---tz_minutes({})--tz_offset({})---".format(tz_sign, tz_hours, tz_minutes, tz_offset))
        # 创建时区对象
        return timezone(timedelta(seconds=tz_offset))

    # def _parse_git_object(self, git_dir, obj_hash):
    #     """解析Git对象文件"""
    #     
    #     try:
    #         obj_path = os.path.join(git_dir, 'objects', obj_hash[:2], obj_hash[2:])
    #         with open(obj_path, 'rb') as f:
    #             raw_data = zlib.decompress(f.read())
    #             return raw_data.split(b'\x00', 1)[1].decode('utf-8', 'ignore')
    #     except Exception as e:
    #         raise UserError(_("Git解析错误: %s") % str(e))

    def _parse_git_object(self, git_dir, obj_hash):
        """解析Git对象文件（支持松散对象、packed objects、多编码）"""
        # pip install gitdb, chardet
        _logger.info("-----_parse_git_object---commit_hash(%s)", obj_hash)

        # ------------------------------
        # 1. 哈希合法性校验（独立功能）
        # ------------------------------
        self._validate_git_hash(obj_hash)

        try:
            # ------------------------------
            # 2. 获取原始数据（支持 packed objects）
            # ------------------------------
            raw_data = None
            obj_path = os.path.join(git_dir, 'objects', obj_hash[:2], obj_hash[2:])
            
            # 优先尝试松散对象
            if os.path.exists(obj_path):
                with open(obj_path, 'rb') as f:
                    raw_data = zlib.decompress(f.read())
            else:
                # 使用 gitdb 解析 pack 文件
                _logger.warning(_("------_parse_git_object--(pip install gitdb)---from gitdb import GitDB---"))
                try:
                    from gitdb import GitDB  # 延迟导入避免依赖问题
                except ImportError:
                    raise UserError(_("解析 Packed Objects 需要安装 gitdb 库：pip install gitdb"))
                obj_db = GitDB(os.path.join(git_dir, 'objects'))
                raw_data = obj_db.stream(obj_hash.encode()).read()

            # ------------------------------
            # 3. 解码数据（支持多编码）
            # ------------------------------
            # 提取内容部分（跳过对象头）
            content = raw_data.split(b'\x00', 1)[1]
            
            # 尝试 UTF-8 解码
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                # 自动检测编码（如 GBK、ISO-8859-1）
                _logger.warning(_("------_parse_git_object---(pip install chardet)---import chardet---"))
                try:
                    import chardet
                except ImportError:
                    raise UserError(_("检测非 UTF-8 编码需要安装 chardet 库：pip install chardet"))
                detected = chardet.detect(content)
                return content.decode(detected['encoding'] or 'latin-1', 'replace')

        except Exception as e:
            _logger.error("解析对象失败，哈希: %s，错误: %s", obj_hash, str(e))
            raise UserError(_("Git解析错误: %s") % str(e))

    def _validate_git_hash(self, hash):
        if not re.match(r'^[0-9a-fA-F]{40}$', hash):
            raise UserError(_("无效的 Git 哈希值: %s") % hash)

    # 新增辅助方法：解析 packed-refs
    def _get_packed_ref(self, git_dir, target_ref):
        packed_refs_path = os.path.join(git_dir, 'packed-refs')
        if not os.path.exists(packed_refs_path):
            return None
        
        with open(packed_refs_path, 'r') as pf:
            for line in pf:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue  # 跳过注释和空行
                if line.endswith(f' {target_ref}'):
                    return line.split()[0]
        return None

    def _get_head_info(self, git_dir):
        """获取HEAD指向的提交哈希值和分支"""
        self._check_git_dir(git_dir)
        try:
            # 解析HEAD文件
            head_path = os.path.join(git_dir, 'HEAD')
            with open(head_path, 'r') as f:
                ref = f.read().strip()
            if ref.startswith('ref: '):
                branch_path = ref[5:]
                ref_path = os.path.join(git_dir, branch_path)
                # 优先尝试正常 ref 文件
                if os.path.exists(ref_path):
                    with open(ref_path, 'r') as f:
                        commit_hash = f.read().strip()
                else:
                    # 如果找不到正常的 ref 文件，尝试解析 packed-refs
                    commit_hash = self._get_packed_ref(git_dir, branch_path)
                    if not commit_hash:
                        raise UserError(f"Ref {branch_path} 不存在于 packed-refs")
                branch = branch_path.split('/')[-1]
            else:
                commit_hash = ref
                branch = 'detached'
            return {
                'hash': commit_hash,
                'branch': branch
            }
        except Exception as e:
            raise UserError(_("获取Git仓库的HEAD信息错误: %s") % str(e))
    
    def _get_latest_commit_data(self, git_dir, commit_hash):
        """获取最新提交数据"""
        return self._parse_git_object(git_dir, commit_hash)

    def _get_date_from_commit_data(self, commit_data, with_timezone=True):
        """从提交数据中提取日期"""
        date_str = self._get_time_info_from_commit_data(commit_data)['date_str']
        tz = self._get_timezone(commit_data)
        try:
            # 尝试直接转换Unix时间戳
            timestamp = int(date_str)
        except ValueError:
            # 如果不是时间戳，则使用安全的方式处理日期字符串
            _logger.warning("无法将 %s 解析为时间戳，使用当前时间", date_str)
            raise UserError(_("解析时间戳({})错误".format(date_str)))

        # 确保时间戳在合理范围内
        if timestamp < 0 or timestamp > 2147483647:  # 2147483647 是 Unix 时间戳上限
            _logger.warning("无法将 %s 解析为时间戳，使用当前时间", date_str)
            raise UserError(_("{}超过unix时间戳范围0~2147483647".format(date_str)))  

        local_dt = datetime.fromtimestamp(timestamp)
        print("-----_get_date_from_commit_data--not--with_timezone---local_dt({})----".format(local_dt))
        if with_timezone:
            # 创建带有时区的datetime对象
            local_dt = datetime.fromtimestamp(timestamp, tz)
            print("-----_get_date_from_commit_data--with_timezone---local_dt({})----".format(local_dt))
        # 转换为 Odoo 上下文时区
        # formatted_date = fields.Datetime.to_string(fields.Datetime.context_timestamp(self, local_dt))
        return local_dt

    def _get_commit_info(self, commit_data):
        """获取最新提交信息"""
        # message = commit_data.split('\n\n', 1)[1].split('\n')[0]
        local_dt = self._get_date_from_commit_data(commit_data, with_timezone=True)
        return {
            # 'message': message,
            'data': commit_data,
            'date': fields.Datetime.to_string(local_dt),
            # 'date': formatted_date,
        }

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
        git_dir = self._get_git_dir()
        self._check_git_dir(git_dir)
        _logger.info("-----refresh_git_info--找到--Git目录: %s", git_dir)
        # self.search([]).unlink()  # 清理旧记录
        info = self._get_head_info(git_dir)
        commit_hash = info['hash']
        branch = info['branch']
        commit_data = self._get_latest_commit_data(git_dir, commit_hash)
        commit_info = self._get_commit_info(commit_data)
        release_tag = self._get_latest_tag(git_dir)
        
        # 查询最近一条记录
        latest_record = self.search([], order='create_date desc', limit=1)
        
        # 如果存在记录且hash值相同，则跳过创建
        if latest_record and latest_record.commit_hash == commit_hash:
            _logger.info("检测到相同的commit hash，跳过创建新记录")
            # self.env.user.notify_success(message='已是最新了')
            raise UserError(_("已是最新了"))
            
        # 创建新记录
        self.create({
            'commit_hash': commit_hash,
            'commit_data': commit_info['data'],
            # 'commit_date': commit_info['date'],
            'branch_name': branch,
            'release_tag': release_tag
        })

    # 使用交互式命令进行调试
    # python odoo\odoo-bin shell -c odoo.conf
    # env = self.env['stc.git.info']
    # records = env.search([('field', '=', value)])  # 查询记录
    # self.env['stc.git.info'].debug()
    def debug(self):
        git_dir = self._get_git_dir()
        print("Hello git_dir={}, timezone={}".format(git_dir, self._get_timezone()))
        info = self._get_head_info(git_dir)
        commit_hash = info['hash']
        # branch = info['branch']
        commit_data = self._get_latest_commit_data(git_dir, commit_hash)
        commit_info = self._get_commit_info(commit_data)
        print("--------commitinfo({})----raw({})----".format(commit_info, commit_data))
