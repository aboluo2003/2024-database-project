from flask import Flask, request, redirect, url_for, render_template, flash, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import abort

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, 
    BooleanField, SelectField, 
    SubmitField, RadioField, 
    DateTimeField, TimeField, FileField
)
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError

from urllib.parse import urlparse, urljoin
from datetime import datetime
from functools import partial

import traceback
import imghdr
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '123456'
app.config['MYSQL_DB'] = 'dormitory'
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_PORT'] = 3306

app.config['UPLOAD_FOLDER'] = 'uploads'

# 创建一个符号链接
static_folder = os.path.join(app.root_path, 'static')
upload_folder_link = os.path.join(static_folder, 'uploads')
# if not os.path.exists(upload_folder_link) :
#     os.symlink(app.config['UPLOAD_FOLDER'], upload_folder_link)

mysql = MySQL(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, account_type) :
        super().__init__()
        self.id = id
        self.username = username
        self.password = password
        self.account_type = account_type
    
    def check_password(self, password) :
        return self.password == password    

    def is_admin(self): 
        return self.account_type == 1
    def is_student(self) :
        return self.account_type == 0
    def is_root(self) :
        return self.account_type == -1

    @classmethod
    def get(cls, id=None, *, username=None) :
        cur = mysql.connection.cursor()
        if id is not None :
            cur.execute(f'select * from account where UID = {id}')
        else :
            cur.execute(f"select * from account where username = '{username}'")
        data = cur.fetchone()
        cur.close()
        if data is None :
            return None
        return cls(*data)
    
    def get_sid(self) :
        id_name, table_name = ('SID', 'Student') if self.account_type == 0 else ('GID', 'Administrator')
        cur = mysql.connection.cursor()
        cur.execute(f'select {id_name} from {table_name} where UID = {self.id}')
        data = cur.fetchone()
        cur.close()
        if data is None :
            return None
        return data[0]
    
    def has_room(self) :
        if self.account_type != 0 :
            return False
        cur = mysql.connection.cursor()
        cur.execute(f'select BID from Student where UID = {self.id}')
        data = cur.fetchone()
        cur.close()
        # print(data)
        return data is not None and data[0] is not None

    def get_avatar_path(self) :
        if hasattr(self, 'avatar_path') :
            return self.avatar_path
        cur = mysql.connection.cursor()
        table = 'student' if self.is_student() else 'administrator'
        cur.execute(f'select avatar_path from {table} where uid = {self.id}')
        data = cur.fetchone()
        self.avatar_path = data[0] if data else None
        return self.avatar_path

@login_manager.user_loader
def load_user(user_id):
  return User.get(user_id)

@app.route('/')
@login_required
def index():
    # print(current_user.username)
    return redirect('/dashboard')
    id = 0
    cur = mysql.connection.cursor()
    cur.execute(f'select * from account where UID = {id}')
    data = cur.fetchone()
    cur.close()
    return str(data)

# 返回上个页面
def last_page() :
    referer = request.headers.get('Referer')
    if referer:
        return redirect(referer)
    # 如果没有Referer头，可以返回主页或者其他默认页面
    return redirect(url_for('index'))

def render_base_template(*args, **kwargs) :
    if not current_user.is_authenticated :
        apps = [
            ('注册', '/register'),
            ('访客登记', '/visitor/record')
        ]
        return render_template(*args, apps=apps, **kwargs)
    apps = [('个人信息', '/profile')]
    if current_user.is_student() :
        if current_user.has_room() :
            apps.append(('我的房间', '/myroom'))
            apps.append(('住宿信息/退宿', '/lodging'))
            apps.append(('维修申报', '/maintenance_report'))
        else :
            apps.append(('入住登记', '/checkin'))
    else :
        apps.append(('住宿信息', '/lodging'))
        apps.append(('学生信息', '/students'))
    apps.append(('维修申报记录', '/maintenance_reports'))
    apps.append(('访客信息', '/visitor'))
    apps.append(('公寓信息公示', '/building'))
    return render_template(*args, apps=apps, **kwargs)

@app.route('/dashboard')
@login_required
def dashboard() :
    return render_base_template('welcome.html')

class StudentForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=15)])
    password = PasswordField('密码', validators=[DataRequired()])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    sid = StringField('学号', validators=[DataRequired()])
    name = StringField('姓名', validators=[DataRequired()])
    phone = StringField('联系电话', validators=[DataRequired()])
    email = StringField('电子邮箱', validators=[DataRequired()])
    department = StringField('院系', validators=[DataRequired()])
    gender = SelectField('性别', choices=[('女', '女'), ('男', '男')])
    submit = SubmitField('注册')

class AdminForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=15)])
    password = PasswordField('密码', validators=[DataRequired()])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    gid = StringField('工号', validators=[DataRequired()])
    name = StringField('姓名', validators=[DataRequired()])
    phone = StringField('联系电话', validators=[DataRequired()])
    email = StringField('电子邮箱', validators=[DataRequired()])
    submit = SubmitField('注册')

class RegistrationForm(FlaskForm):
    registration_type = RadioField('注册类型', choices=[('admin', '公寓管理员'), ('student', '学生')])
    submit = SubmitField('下一步')

class InfoStudentForm(StudentForm):
    password = PasswordField('密码（修改信息时需要输入）', validators=[DataRequired()])
    new_password = PasswordField('新密码（修改密码时需要输入）', validators=[])
    confirm_password = PasswordField('确认密码（修改密码时需要输入）', validators=[])
    submit = SubmitField('修改')

class InfoAdminForm(AdminForm):
    password = PasswordField('密码（修改信息时需要输入）', validators=[DataRequired()])
    new_password = PasswordField('新密码（修改密码时需要输入）', validators=[])
    confirm_password = PasswordField('确认密码（修改密码时需要输入）', validators=[])
    submit = SubmitField('修改')

class AdminViewStudentForm(StudentForm) :
    password = None
    confirm_password = None
    submit = SubmitField('修改')

def get_student_info(uid, fields=None) :
    conn = mysql.connect
    cursor = conn.cursor()
    
    if fields is None :
        query_str = '*'
    else :
        query_str = ', '.join(fields)
    
    cursor.execute(f'select {query_str} from student where uid={uid}')
    data = cursor.fetchone()[0]
    cursor.close()
    return data
    
@app.route('/profile', methods=['GET', 'POST'])
@app.route('/profile/<int:uid>', methods=['GET', 'POST'])
@login_required
def profile(uid=None) :
    current_user.get_avatar_path()
    
    # 查看和修改 uid 个人账号
    if uid is not None and uid != current_user.id:
        if current_user.is_student() :
            flash('您没有权限访问当前页面')
            return last_page()
        
        back = request.args.get('back', '/lodging')
        
        # 由 admin 访问
        fields = ['username', 'sid', 'name', 'department', 'phone', 'email', 'gender']
        query_str = ', '.join(fields)
        
        conn = mysql.connect
        cursor = conn.cursor()
        cursor.execute(f'select {query_str} from student, account where student.uid={uid} and student.uid=account.uid')
        data = cursor.fetchone()
        cursor.close()
        
        if not data :
            flash('当前学生不存在或您没有权限访问当前页面')
            return last_page()
        
        form = AdminViewStudentForm(form=request.form)
        if form.validate_on_submit() :
            update_str = ', '.join([key + ' = %s' for key in fields if key != 'username'])
            form_data = tuple(getattr(form, field).data for field in fields if field != 'username')
            try :
                conn = mysql.connect
                cursor = conn.cursor()
                cursor.execute('update student set {upd} where uid = {uid}'.format(upd=update_str, uid=uid), form_data)
                cursor.execute('update account set username = %s where uid = %s', (form.username.data, uid))
                
                conn.commit()
                cursor.close()
            except Exception as e :
                conn.rollback()
                flash('修改时发生错误，请联系管理员！')
                traceback.print_exc()
                return render_base_template('update_lodging.html', form=form, form_title='修改学生信息', back=back)
            return redirect(back)
        else :
            for fieldname, val in zip(fields, data) :
                getattr(form, fieldname).data = val
            form.sid.render_kw = {'readonly': True}
        return render_base_template('update_lodging.html', form=form, form_title='修改学生信息', back=back)
    
    render = partial(render_base_template, 'profile.html', form_title='个人信息')
        
    if current_user.account_type == 0 :
        form = InfoStudentForm(form=request.form)
        
        fields = ['username', 'sid', 'name', 'department', 'phone', 'email', 'gender']
        query_str = ', '.join(fields)
        
    elif current_user.account_type == 1 :
        form = InfoAdminForm(form=request.form)
        
        fields = ['username', 'gid', 'name', 'phone', 'email']
        query_str = ', '.join(fields)

    form.username.render_kw = {'readonly': True}

    # print(form)
    # print(f"status = {form.validate_on_submit()}")
    
    if form.validate_on_submit() :
        password = request.form['password']
            
        if len(password) == 0 or not current_user.check_password(password) :
            flash('密码不正确')
            res = Response(render(form=form), status="412")
            abort(res)

        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password and len(confirm_password) > 0 :
            flash('两次输入的密码不一致')
            res = Response(render(form=form), status="412")
            abort(res)
        
        name = form.name.data
        phone = form.phone.data
        email = form.email.data
        if current_user.account_type == 0 :
            sid = form.sid.data
            # print(f'sid = {sid}')
            department = form.department.data
            gender = form.gender.data
        else :
            gid = form.gid.data
        
        conn = mysql.connect
        cursor = conn.cursor()
        
        try :
            if len(confirm_password) > 0 :
                cursor.execute(f"update Account set user_password = '{new_password}' where UID = {current_user.id}")
            if current_user.account_type == 0 :
                cursor.execute(f"update Student set sid = '{sid}', name = '{name}', phone = '{phone}', email = '{email}', \
                    gender = '{gender}', department = '{department}' where uid = '{current_user.id}'")
            elif current_user.account_type == 1 :
                cursor.execute(f"update Administrator set gid = '{gid}', name = '{name}', phone = '{phone}', email = '{email}' \
                    where uid = {current_user.id}")
            conn.commit()
        except Exception as e :
            conn.rollback()
            flash('修改时发生错误，请联系管理员！')
            traceback.print_exc()
            return render(form=form)
            
        flash('修改成功！')
        return render(form=form)
    else :
        cur = mysql.connection.cursor()
        if current_user.is_student() :
            cur.execute(f'select {query_str} from account, student where account.uid = student.uid and account.uid = {current_user.id}')
        else :
            cur.execute(f'select {query_str} from account, administrator where account.uid = administrator.uid \
                and administrator.uid = {current_user.id}')
        data = cur.fetchone()
        cur.close()
        
        for field_name, val in zip(fields, data) :
            getattr(form, field_name).data = val
    
    # if hasattr(form, 'sid') :
    #     form.sid.render_kw = {'readonly': True}
    # if hasattr(form, 'gid') :
    #     form.gid.render_kw = {'readonly': True}
                
    return render(form=form)

@app.route('/students')
def students() :
    if current_user.is_student() :
        res = Response(redirect('maintenance_reports'), status=403)
        return res
    
    fields = ['SID', 'name', 'department', 'phone', 'email', 'gender', 'BID', 'RID', 'UID']
    query_str = ', '.join(fields)
    
    gid = current_user.get_sid()
    
    conn = mysql.connection
    cursor = conn.cursor()   
    # cursor.execute(f'select {query_str} from student')
    cursor.execute("""
        select {qry} from student
    """.format(qry=query_str, id=gid))
    data = cursor.fetchall()
    cursor.close()
    
    table_data = []
    for batch in data :
        table_data.append((
            *batch[: -1], 
            '<a href="/lodging/{id}?back=/students">修改住宿信息</a> <a href="/profile/{id}?back=/students">修改学生信息</a>'.format(id=batch[-1])
        ))
    
    columns = ['学号', '姓名', '院系', '电话', '邮箱', '性别', '宿舍楼', '住宿房间', '操作']
    return render_base_template('table.html', columns=columns, table_data=table_data, table_name='学生信息')


def validate_image(form, field) :
    if field.data and not imghdr.what(field.data) :
        raise ValidationError('上传的文件不是有效的图像文件。')

class AvatarForm(FlaskForm):
    avatar = FileField('选择头像', validators=[DataRequired(), validate_image])
    submit = SubmitField('上传头像')

def generate_filename() :
    uid = current_user.id
    now = datetime.now()
    unique_filename = now.strftime('%Y%m%d%H%M%S%f')
    return f'{uid}-{unique_filename}'

@app.route('/profile/avatar', methods=['POST', 'GET'])
@login_required
def upload_avatar() :
    form = AvatarForm(form=request.form)
    old_avatar_path = current_user.get_avatar_path()
    if form.validate_on_submit() :
        file = form.avatar.data
        suffix = file.filename.split('.')[-1]
        filename = generate_filename() + '.' + suffix
        avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        save_path = os.path.join(static_folder, avatar_path)
        file.save(save_path)
        current_user.avatar_path = avatar_path
        
        if old_avatar_path :
            old_save_path = os.path.join(static_folder, old_avatar_path)
            os.remove(old_save_path)
        
        try :
            conn = mysql.connect
            cursor = conn.cursor()
            
            if current_user.is_student() :
                cursor.execute('update student set avatar_path = %s where uid = %s', (avatar_path, current_user.id))
            else :
                cursor.execute('update administrator set avatar_path = %s where uid = %s', (avatar_path, current_user.id))
            
            conn.commit()
        except Exception as e :
            conn.rollback()
            traceback.print_exc()
            flash('更新头像时出现错误，请联系管理员！')
    
    return render_base_template('avatar.html', form=form)

### 住宿相关

# 定义入住表单
class CheckinForm(FlaskForm):
    
    BID = StringField('宿舍楼编号', validators=[DataRequired()])
    RID = StringField('房间编号', validators=[DataRequired()])
    SID = StringField('学号', validators=[DataRequired()])
    submit = SubmitField('提交')

# 定义退宿表单
class CheckoutForm(CheckinForm):
    submit = SubmitField('退宿')

# 定义 lodging 路由
@app.route('/lodging', methods=['GET', 'POST'])
@app.route('/lodging/<int:uid>', methods=['GET', 'POST'])
@login_required
def lodging(uid=None):
    if uid is not None :
        if current_user.is_student() :
            flash('您没有权限访问该页面')
            return last_page()
        
        back = request.args.get('back', '/lodging')
        
        # 建立数据库连接
        conn = mysql.connection
        cursor = conn.cursor() 
        
        cursor.execute(f'select SID, BID, RID from student where UID = {uid}')
        data = cursor.fetchone()
        cursor.close()
        
        if data is None :
            flash('不存在该学生')
            return redirect('/lodging')
        
        form = CheckinForm(form=request.form)
        
        if form.validate_on_submit() :
            form_data = (data[0], form.BID.data, form.RID.data)
            if form_data != data :
                try :
                    cursor = conn.cursor()
                    if data[1] and data[2] :
                        cursor.callproc('checkout_student', (data[0], ))
                    cursor.callproc('checkin_student', form_data)
                except :
                    conn.rollback()
                    traceback.print_exc()
                    flash('修改时发生错误，请联系管理员')
                    return render_base_template('update_lodging.html', form=form, form_title='学生住宿信息', back=back)
            flash('修改成功')
            return redirect(back)
        for fieldname, val in zip(['SID', 'BID', 'RID'], data) :
            getattr(form, fieldname).data = val
        form.SID.render_kw = {'readonly': True}
        return render_base_template('update_lodging.html', form=form, form_title='学生住宿信息', back=back)
        
    if current_user.is_student() :
        # 检查学生是否已入住
        if not current_user.has_room():
            flash('您当前还未入住，请先入住再查看住宿信息')
            return redirect(url_for('checkin'))

        form = CheckoutForm()
        
        # 建立数据库连接
        conn = mysql.connection
        cursor = conn.cursor()   
        
        cursor.execute(f'select SID, BID, RID from student where UID = {current_user.id}')
        data = cursor.fetchone()

        for fieldname, val in zip(['SID', 'BID', 'RID'], data) :
            getattr(form, fieldname).data = val
            getattr(form, fieldname).render_kw = {'readonly': True}
            
        if form.validate_on_submit():
            try:
                # 调用 checkout_student 存储过程
                cursor.callproc('checkout_student', (data[0], ))
                conn.commit()
                flash('退宿成功！')
                return redirect(url_for('checkin'))
            except Exception as e:
                conn.rollback()
                flash('退宿时发生错误，请联系管理员！')
                return render_base_template('form_template.html', form=form, form_title="住宿信息")

        return render_base_template('form_template.html', form=form, form_title="住宿信息")
    
    fields = ['SID', 'name', 'department', 'phone', 'email', 'gender', 'BID', 'RID', 'UID']
    query_str = ', '.join(fields)
    
    gid = current_user.get_sid()
    
    conn = mysql.connection
    cursor = conn.cursor()   
    # cursor.execute(f'select {query_str} from student')
    cursor.execute("""
        select {qry} from student
            where exists (
                select * from Manage where Manage.GID = '{id}' and Manage.BID = student.BID
            )
    """.format(qry=query_str, id=gid))
    data = cursor.fetchall()
    cursor.close()
    
    table_data = []
    for batch in data :
        table_data.append((
            *batch[: -1], 
            '<a href="/lodging/{id}">修改住宿信息</a> <a href="/profile/{id}">修改学生信息</a>'.format(id=batch[-1])
        ))
    
    columns = ['学号', '姓名', '院系', '电话', '邮箱', '性别', '宿舍楼', '住宿房间', '操作']
    return render_base_template('table.html', columns=columns, table_data=table_data, table_name='住宿信息')

# 定义入住处理路由
@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    if not current_user.is_student() :
        return last_page()
    if current_user.has_room() :
        return redirect(url_for('lodging'))
    
    form = CheckinForm(form=request.form)
    form.SID.data = current_user.get_sid()
    form.SID.render_kw = {'readonly': True}
    
    if form.validate_on_submit():
        # 获取表单数据
        BID = form.BID.data
        RID = form.RID.data
        SID = form.SID.data

        conn = mysql.connect
        cursor = conn.cursor()
        
        try:
            # 调用存储过程
            cursor.callproc('checkin_student', (SID, BID, RID))
            conn.commit()
            flash('入住成功！')
            return redirect(url_for('lodging'))
        except Exception as e:
            conn.rollback()
            traceback.print_exc()
            flash(f'入住时发生错误，请联系管理员！错误信息：{str(e)}')
            return render_base_template('form_template.html', form=form, form_title="入住信息登记")
    return render_base_template('form_template.html', form=form, form_title="入住信息登记")

### 房间信息

# 定义房间信息查看的路由
@app.route('/room_info/<bidrid>')
@login_required
def room_info(bidrid):
    tmp = bidrid.split('-')
    if len(tmp) != 2 :
        flash('无效的房间号')
        return last_page()
    bid, rid = tmp
    
    # 使用 cursor 执行 SQL 查询语句
    cursor = mysql.connection.cursor()
    cursor.execute("select capacity, occupancy from Room where BID = %s and RID = %s", (bid, rid))
    room_info = cursor.fetchone()
    
    if not room_info :
        flash('房间不存在或您没有权限访问该页面')
        return last_page()
    
    # 学生只能查看自己的房间信息
    if current_user.is_student() :
        cursor.execute(f'select bid, rid from student where uid = {current_user.id}')
        sbid, srid = cursor.fetchone()
        if sbid != bid or srid != rid :
            flash('房间不存在或您没有权限访问该页面')
            return last_page()
    
    cursor.execute("select name, SID, phone, email from Student where BID = %s and RID = %s", (bid, rid))
    students_info = cursor.fetchall()
    
    cursor.close()
    
    # 渲染模板，传递房间信息和居住学生信息
    return render_base_template('room_info.html', room_info=room_info, students_info=students_info)

@app.route('/myroom')
@login_required
def myroom():
    # 使用 cursor 执行 SQL 查询语句
    cursor = mysql.connection.cursor()
    cursor.execute("""
        select BID, RID
        from Student
        where UID = %s
    """, (current_user.id,))
    my_room = cursor.fetchone()
    
    if not my_room:
        flash('您没有分配的房间。')
        return last_page()
    
    bid, rid = my_room
    
    cursor.execute("select capacity, occupancy from Room where BID = %s and RID = %s", (bid, rid))
    room_info = cursor.fetchone()
    
    if not room_info:
        flash('房间不存在或您没有权限访问该页面')
        return last_page()
    
    cursor.execute("select name, SID, phone, email from Student where BID = %s and RID = %s", (bid, rid))
    students_info = cursor.fetchall()
    
    cursor.close()
    
    # 渲染模板，传递房间信息和居住学生信息
    return render_base_template('room_info.html', room_info=room_info, students_info=students_info)


### 公寓信息

@app.route('/building')
@login_required
def building_info():
    # 使用 cursor 执行 SQL 查询语句
    cursor = mysql.connection.cursor()
    cursor.execute("""
        select B.BID, B.capacity, B.occupancy
        from Building B
    """)
    buildings_info = cursor.fetchall()
    
    # 获取管理员信息
    cursor.execute("""
        select A.GID, A.name, A.phone, A.email, M.BID
        from Administrator A, Manage M where A.GID = M.GID
    """)
    administrators_info = cursor.fetchall()
    
    # 将管理员信息按公寓楼分组
    buildings_with_admins = {}
    for admin in administrators_info:
        if admin[4] not in buildings_with_admins:
            buildings_with_admins[admin[4]] = []
        buildings_with_admins[admin[4]].append({
            'name': admin[1],
            'phone': admin[2],
            'email': admin[3]
        })
    
    # 获取房间信息
    cursor.execute("""
        select R.BID, R.RID, R.capacity, R.occupancy
        from Room R
    """)
    rooms_info = cursor.fetchall()
    
    cursor.close()
    
    # 将查询结果分组，按公寓 BID 分组
    buildings_with_rooms = {}
    for building in buildings_info:
        bid = building[0]
        buildings_with_rooms[bid] = {
            'info': building,
            'admins': buildings_with_admins.get(bid, []),
            'rooms': []
        }
    
    for room in rooms_info:
        bid = room[0]
        buildings_with_rooms[bid]['rooms'].append({
            'RID': room[1],
            'capacity': room[2],
            'occupancy': room[3]
        })
    
    # 渲染模板，传递公寓和房间信息
    return render_base_template('building.html', buildings_with_rooms=buildings_with_rooms)

### 维修申报相关

# 定义维修记录表单
class DetailedMaintenanceForm(FlaskForm):
    MID = StringField('维修记录编号', validators=[DataRequired()])
    BID = StringField('宿舍楼编号', validators=[DataRequired()])
    RID = StringField('房间编号', validators=[DataRequired()])
    SID = StringField('申请人学号', validators=[DataRequired()])
    application_date = DateTimeField('申请日期', validators=[DataRequired()])
    updated_date = DateTimeField('更新日期', validators=[DataRequired()], default=datetime.now)
    progress = SelectField('进度', choices=[
        ('0', '已提交'),
        ('1', '正在处理'),
        ('2', '已经处理结束'),
        ('-1', '已驳回'),
        ('-2', '异常')
    ])
    submit = SubmitField('提交')

# 定义维修记录详细信息路由
@app.route('/maintenance/<int:mid>', methods=['GET', 'POST'])
@login_required
def maintenance(mid) :# 建立数据库连接
    if current_user.is_student() :
        res = Response(redirect('maintenance_reports'), status=403)
        return res
    
    cur = mysql.connection.cursor()

    fields = ['MID', 'BID', 'RID', 'SID', 'application_date', 'updated_date', 'progress']

    # 查询维修记录
    cur.execute("select * from Maintenance where MID = %s", (mid,))
    data = cur.fetchone()

    # 关闭数据库连接
    cur.close()

    # 检查是否找到记录
    if not data:
        flash('维修记录不存在！')
        return redirect(url_for('maintenance_reports'))

    # 创建表单实例并预填充数据
    form = DetailedMaintenanceForm(form=request.form)
    render = partial(render_base_template, 'maintenance_report.html', form_title='维修记录')
    
    # render = partial(render_base_template, 'form_template.html', form_title='维修记录')
    
    # 表单提交处理
    if form.validate_on_submit():
        # 获取表单数据
        BID = form.BID.data
        RID = form.RID.data
        SID = form.SID.data
        application_date = form.application_date.data
        updated_date = datetime.now()
        progress = form.progress.data

        try :
            # 建立数据库连接
            cur = mysql.connection.cursor()

            # 更新维修记录
            cur.execute("update Maintenance set BID = %s, RID = %s, SID = %s, application_date = %s, updated_date = %s, progress = %s WHERE MID = %s", 
                    (BID, RID, SID, application_date, updated_date, progress, mid))
            mysql.connection.commit()
        except Exception as e :
            mysql.connection.rollback()
            traceback.print_exc()
            flash(f'发生错误，请联系管理员！错误信息：{str(e)}')
            return render(form=form)

        # 关闭数据库连接
        cur.close()
        
        flash('维修记录已更新！')
        return redirect(url_for('maintenance_reports'))
    else :
        for fieldname, val in zip(fields, data) :
            getattr(form, fieldname).data = val if fieldname != 'progress' else str(val)
        form.MID.render_kw = {'readonly': True}

    # 渲染模板
    return render(form=form)

# 定义一个新路由用于删除维修记录
@app.route('/delete_maintenance/<int:mid>', methods=['GET', 'POST'])
@login_required
def delete_maintenance(mid):
    # 获取当前用户的信息
    user = current_user
    
    if not user.is_admin():
        flash("您没有权限删除该维修记录")
        return redirect('/maintenance_reports')

    # 建立数据库连接
    conn = mysql.connect
    cur = conn.cursor()

    # 查询维修记录
    cur.execute("select * from Maintenance where MID = %s", (mid,))
    record = cur.fetchone()
    cur.close()

    # 检查记录是否存在
    if record is None:
        flash("维修记录不存在")
        return redirect('/maintenance_reports')

    try :
        # 执行删除操作
        cur = conn.cursor()
        cur.execute("DELETE FROM Maintenance WHERE MID = %s", (mid,))
        conn.commit()
        cur.close()
    except Exception as e :
        conn.rollback()
        traceback.print_exc()
        flash('删除时发生错误，请联系管理员')
        return redirect('/maintenance_reports')

    # 返回成功消息
    flash("维修记录已删除")
    return redirect('/maintenance_reports')

@app.route('/maintenance_reports')
@login_required
def maintenance_reports():
    progress_dict = {
        0: '已提交',
        1: '正在处理',
        2: '已经处理结束',
        -1: '已驳回',
        -2: '异常'
    }
    flg_admin = not current_user.is_student()
    if not flg_admin :
        try:
            # 获取当前用户的 SID
            current_user_id = current_user.get_sid()

            # 执行SQL查询以获取所有与当前用户相关的已经申请过的维修申报记录
            cur = mysql.connection.cursor()
            cur.execute("select MID, BID, RID, SID, application_date, updated_date, progress from Maintenance where SID = %s", (current_user_id,))
            maintenance_records = cur.fetchall()
            cur.close()

            # 将查询结果转换为字典列表
            table_data = []
            for record in maintenance_records:
                table_data.append((
                    *record[0: 4], 
                    record[4].strftime('%Y-%m-%d') if record[4] else None,
                    record[5].strftime('%Y-%m-%d') if record[5] else None,
                    progress_dict[record[6]]
                ))
            
            print(table_data)
            
            # 准备列名列表
            columns = ['记录编号', '楼号', '房间号', '申请人学号', '申请日期', '更新日期', '进度']
            
            # 将数据传递给模板
            return render_base_template('table.html', table_name='维修申报记录', columns=columns, table_data=table_data)
        except Exception as e:
            # 如果发生错误，显示错误消息
            flash(f"发生错误，请联系管理员。错误信息：{e}")
            return render_base_template('table.html', table_name='维修申报记录', columns=columns, table_data=[])
    else :
        try:
            cur = mysql.connection.cursor()
            cur.execute("select MID, BID, RID, SID, application_date, updated_date, progress from Maintenance")
            maintenance_records = cur.fetchall()
            cur.close()

            # 将查询结果转换为字典列表
            table_data = []
            for record in maintenance_records:
                table_data.append((
                    *record[0: 4], 
                    record[4].strftime('%Y-%m-%d') if record[4] else None,
                    record[5].strftime('%Y-%m-%d') if record[5] else None,
                    progress_dict[record[6]],
                    f'<a href="/maintenance/{record[0]}">查看/修改</a> <a href="/delete_maintenance/{record[0]}">删除</a>'
                ))
            
            print(table_data)
            
            # 准备列名列表
            columns = ['记录编号', '楼号', '房间号', '申请人学号', '申请日期', '更新日期', '进度', '操作']
            
            # 将数据传递给模板
        except Exception as e:
            # 如果发生错误，显示错误消息
            flash(f"发生错误，请联系管理员。错误信息：{e}")
            return render_base_template('table.html', table_name='维修申报记录', columns=columns, table_data=[])
        return render_base_template('table.html', table_name='维修申报记录', columns=columns, table_data=table_data)
        
class MaintenanceForm(FlaskForm):
    BID = StringField('宿舍楼编号', validators=[DataRequired()])
    RID = StringField('房间编号', validators=[DataRequired()])
    SID = StringField('申请人学号', validators=[DataRequired()])
    submit = SubmitField('提交维修申报') 

# 实现 maintenance_report 函数
@app.route('/maintenance_report', methods=['GET', 'POST'])
@login_required
def maintenance_report():
    if not current_user.has_room():
        flash('您当前还未入住，无法提交维修申报。')
        return redirect(url_for('checkin'))
    
    
    # 建立数据库连接
    conn = mysql.connection
    cursor = conn.cursor()
    
    cursor.execute(f'select sid, bid, rid from student where uid = {current_user.id}')
    sid, bid, rid = cursor.fetchone()

    if bid is None or rid is None :
        flash('无法获取您的住宿信息，请联系管理员。')
        return redirect(url_for('checkin'))

    # 创建表单实例并设置 render_kw 使得它不可修改
    form = MaintenanceForm()
    form.BID.render_kw = {'readonly': True}
    form.RID.render_kw = {'readonly': True}
    form.SID.render_kw = {'readonly': True}
    form.BID.data = bid
    form.RID.data = rid
    form.SID.data = sid

    if form.validate_on_submit():
        # 获取表单数据
        # application_date = form.application_date.data
        # 确保所有字段都有值
        # if not application_date:
        #     application_date = datetime.now()
        # form.application_date.data = application_date

        try:
            # 调用存储过程或执行SQL查询来提交维修申报
            # 这里假设存储过程已经创建，并且可以处理 application_date 字段
            cursor.execute("insert into Maintenance (BID, RID, SID, application_date, updated_date, progress) values (%s, %s, %s, %s, %s, 0)", 
                           (bid, rid, sid, datetime.now(), datetime.now()))
            conn.commit()
            flash('维修申报提交成功！')
            return redirect(url_for('maintenance_reports'))
        except Exception as e:
            conn.rollback()
            traceback.print_exc()
            flash('维修申报提交时发生错误，请联系管理员！')
            return render_base_template('form_template.html', form=form, form_title="维修申报")

    return render_base_template('form_template.html', form=form, form_title="维修申报")

### 登录相关

def is_safe_url(target):
    """
    Check if the target URL is safe.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated :
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.get(username=username)
        if user == None :
            flash('用户不存在或密码错误！')
            res = Response(render_base_template('login.html'), status='412')
            abort(res)
        
        if not user.check_password(password) :
            flash('用户不存在或密码错误！')
            res = Response(render_base_template('login.html'), status='412')
            abort(res)
        
        # print(f"username = {username}, password = {password}")
        login_user(user)
        
        next_url = request.args.get('next')
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for('index'))
    return render_base_template('login.html')

@app.route('/err')
def error() :
    return "Error"

@app.route('/register', methods=['GET', 'POST'])
@app.route('/register/<register_type>', methods=['GET', 'POST'])
def register(register_type=None):
    if register_type == 'student' :
        form = StudentForm(request.form)
        if request.method == 'POST' :
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            
            if password != confirm_password :
                # TODO 提示信息
                flash('两次输入的密码不一致')
                res = Response(render_base_template('register_student.html', form=form, form_title="学生注册"), status="412")
                abort(res)
                
            username = form.username.data
            password = form.password.data
            sid = form.sid.data
            name = form.name.data
            phone = form.phone.data
            email = form.email.data
            department = form.department.data
            gender = form.gender.data
            
            conn = mysql.connect
            cursor = conn.cursor()
            
            # 查询Counter表中的uid_count值
            cursor.execute("select val from Counter where name = 'uid_count'")
            uid_count = cursor.fetchone()[0]

            # 使用uid_count值生成UID
            uid = str(uid_count)
            
            try :
                # TODO 用 hash 值存储密码
                cursor.execute("insert into Account (UID, username, user_password, account_type) \
                                    values ('%s', '%s', '%s', %d)" % (uid, username, password, 0))
                cursor.execute(f"insert into Student (SID, name, department, phone, email, gender, UID) \
                                    values ('{sid}', '{name}', '{department}', '{phone}', '{email}', '{gender}', {uid})")
                cursor.execute("update Counter set val = val + 1 where name = 'uid_count'")
                conn.commit()
            except Exception as e :
                conn.rollback()
                flash('注册时发生错误，请联系管理员！')
                traceback.print_exc()
                return render_base_template('register_student.html', form=form, form_title="学生注册")
            
            flash('注册成功！')
            return redirect(url_for('login'))
        return render_base_template('register_student.html', form=form, form_title="学生注册")
    elif register_type == 'admin' :
        form = AdminForm(request.form)
        if request.method == 'POST' :
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            
            if password != confirm_password :
                # TODO 提示信息
                flash('两次输入的密码不一致')
                res = Response(render_base_template('register_student.html', form=form, form_title="管理员注册"), status="412")
                abort(res)
                
            username = form.username.data
            password = form.password.data
            gid = form.gid.data
            name = form.name.data
            phone = form.phone.data
            email = form.email.data
            
            conn = mysql.connect
            cursor = conn.cursor()
            
            # 查询 Counter 表中的 uid_count 值
            cursor.execute("select val from Counter where name = 'uid_count'")
            uid_count = cursor.fetchone()[0]

            # 使用 uid_count 值生成 UID
            uid = str(uid_count)
            
            try :
                # TODO 用 hash 值存储密码
                cursor.execute("insert into Account (UID, username, user_password, account_type) \
                                    values ('%s', '%s', '%s', %d)" % (uid, username, password, 1))
                cursor.execute(f"insert into Administrator (GID, name, phone, email, UID) \
                                    values ('{gid}', '{name}', '{phone}', '{email}', {uid})")
                cursor.execute("update Counter set val = val + 1 where name = 'uid_count'")
                conn.commit()
            except Exception as e :
                conn.rollback()
                flash('注册时发生错误，请联系管理员！')
                traceback.print_exc()
                return render_base_template('register_student.html', form=form, form_title="管理员注册")
            
            flash('注册成功！')
            return redirect(url_for('login'))
        return render_base_template('register_student.html', form=form, form_title="管理员注册")
    form = RegistrationForm(request.form)
    if form.validate_on_submit():
        # 处理表单提交的数据
        registration_type = form.registration_type.data
        return redirect(f'/register/{registration_type}')
    return render_base_template('register_choose.html', form=form);

@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('login'))

### 访客相关功能

# 定义访客表单
class VisitorForm(FlaskForm) :
    name = StringField('访客姓名', validators=[DataRequired()])
    phone = StringField('访客电话', validators=[DataRequired()])
    BID = StringField('宿舍楼编号', validators=[DataRequired()])
    arrive_time = DateTimeField('到达时间', validators=[DataRequired()])
    submit = SubmitField('登记')

# 离开时的表单
class VisitorForm1(VisitorForm) :
    leave_time = DateTimeField('离开时间', validators=[DataRequired()])
    submit = SubmitField('确认离开')

@app.route('/visitor', methods=['GET', 'POST'])
@login_required
def visitor() :
    fields = ['name', 'phone', 'BID', 'arrive_time', 'leave_time']
    
    conn = mysql.connect
    cursor = conn.cursor()
    
    cursor.execute('select * from Visitor')
    data = cursor.fetchall()
    cursor.close()
    
    columns = ['访客记录编号', '访客姓名', '访客电话', '访问宿舍楼编号', '到达时间', '离开时间']
    return render_base_template('table.html', columns=columns, table_data=data, table_name='访客信息')

@app.route('/visitor/record', methods=['GET', 'POST'])
def visitor_report():
    # 从 cookie 中获取访客标识符
    visitor_id = request.cookies.get('visitor_id')
    form = VisitorForm(form=request.form) if not visitor_id else VisitorForm1(form=request.form)
    render = partial(render_base_template, 'form_template.html', form_title="访客登记")
    if form.validate_on_submit():
        # 获取表单数据
        name = form.name.data
        phone = form.phone.data
        BID = form.BID.data
        arrive_time = form.arrive_time.data

        # 设置 cookie
        response = redirect(url_for('visitor_report'))

        # 建立数据库连接
        conn = mysql.connection
        cursor = conn.cursor()

        # 来访登记
        if not visitor_id :
            # 创建唯一标识符
            visitor_id = f"{name}-{phone}-{BID}-{arrive_time}"

            try:
                # 调用存储过程或执行SQL查询来提交访客信息
                cursor.execute("insert into Visitor (name, phone, BID, arrive_time, leave_time) values (%s, %s, %s, %s, null)", 
                            (name, phone, BID, arrive_time))
                conn.commit()
                response.set_cookie('visitor_id', visitor_id)
                flash('访客登记成功！')
                return response
            except Exception as e:
                conn.rollback()
                traceback.print_exc()
                flash(f'访客登记时发生错误，请联系管理员！错误信息：{str(e)}')
                return render(form=form)
        else:
            leave_time = form.leave_time.data
            try:
                cursor.execute("update Visitor set leave_time = %s where name = %s and phone = %s", 
                            (leave_time, name, phone))
                conn.commit()
                response.set_cookie('visitor_id', '', expires=0)
                flash('访客离开登记成功！')
                return response
            except Exception as e:
                conn.rollback()
                traceback.print_exc()
                flash(f'访客登记时发生错误，请联系管理员！错误信息：{str(e)}')
                return render(form=form)
    else :
        frozen_fields = ['arrive_time']
        form.arrive_time.data = datetime.now()
        if visitor_id:
            frozen_fields = ['arrive_time', 'name', 'phone', 'BID', 'arrive_time', 'leave_time']
            # 解析访客标识符
            splitted = visitor_id.split('-')
            name, phone, BID = splitted[0: 3]
            arrive_time = datetime.strptime('-'.join(splitted[3: ]), "%Y-%m-%d %H:%M:%S")
            form.name.data = name
            form.phone.data = phone
            form.BID.data = BID
            form.arrive_time.data = arrive_time

            # 更新离开时间为当前时间
            form.leave_time.data = datetime.now()
        for fieldname in frozen_fields :
            getattr(form, fieldname).render_kw = {'readonly': True}
    return render(form=form)

if __name__ == '__main__':
  app.run(debug=True)
