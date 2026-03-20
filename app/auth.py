from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, login_required, login_user, logout_user

try:
    from .models import User, db
except ImportError:
    from models import User, db

bp = Blueprint('auth', __name__, url_prefix='/auth')


def load_user(user_id):
    return db.session.get(User, int(user_id))


def init_login_manager(app):
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Для доступа к данной странице необходимо пройти процедуру аутентификации.'
    login_manager.login_message_category = 'warning'
    login_manager.user_loader(load_user)
    login_manager.init_app(app)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember_me'))

        if login_value and password:
            user = db.session.execute(db.select(User).filter_by(login=login_value)).scalar()
            if user and user.check_password(password):
                login_user(user, remember=remember)
                flash('Вы успешно аутентифицированы.', 'success')
                next_url = request.args.get('next')
                return redirect(next_url or url_for('index'))

        flash('Введены неверные логин и/или пароль.', 'danger')
    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из учётной записи.', 'info')
    return redirect(url_for('index'))
