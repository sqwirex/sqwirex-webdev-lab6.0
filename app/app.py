import os
from pathlib import Path

from flask import Flask, render_template, send_from_directory
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

try:
    from .auth import bp as auth_bp, init_login_manager
    from .courses import bp as courses_bp
    from .models import Category, Course, Image, User, db
except ImportError:
    from auth import bp as auth_bp, init_login_manager
    from courses import bp as courses_bp
    from models import Category, Course, Image, User, db

app = Flask(__name__)
application = app
app.config.from_pyfile('config.py')

Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

db.init_app(app)
migrate = Migrate(app, db)
init_login_manager(app)


@app.errorhandler(SQLAlchemyError)
def handle_sqlalchemy_error(err):
    error_msg = 'Возникла ошибка при подключении к базе данных. Повторите попытку позже.'
    return f'{error_msg} (Подробнее: {err})', 500


app.register_blueprint(auth_bp)
app.register_blueprint(courses_bp)


@app.route('/')
def index():
    categories = db.session.execute(db.select(Category)).scalars()
    latest_courses = db.session.execute(db.select(Course).order_by(Course.created_at.desc()).limit(6)).scalars()
    return render_template('index.html', categories=categories, latest_courses=latest_courses)


@app.route('/images/<image_id>')
def image(image_id):
    img = db.get_or_404(Image, image_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], img.storage_filename)


def seed_data():
    if db.session.execute(db.select(Category)).first() is None:
        db.session.add_all([
            Category(name='Программирование'),
            Category(name='Математика'),
            Category(name='Языкознание'),
        ])
        db.session.commit()

    if db.session.execute(db.select(User).filter_by(login='user')).scalar() is None:
        user = User(first_name='Иван', last_name='Иванов', middle_name='Иванович', login='user')
        user.set_password('qwerty')
        db.session.add(user)
        db.session.commit()
    else:
        user = db.session.execute(db.select(User).filter_by(login='user')).scalar()

    if db.session.execute(db.select(Course)).first() is None:
        category = db.session.execute(db.select(Category).order_by(Category.id)).scalars().first()
        course = Course(
            name='Введение в Python',
            short_desc='Базовый курс по Python с практическими примерами и домашними заданиями.',
            full_desc=(
                'На курсе вы познакомитесь с синтаксисом Python, типами данных, функциями, '
                'структурами управления и основами работы с файлами. Курс подойдёт для первых шагов '
                'в программировании и для подготовки к более сложным дисциплинам.'
            ),
            category_id=category.id,
            author_id=user.id,
        )
        db.session.add(course)
        db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == '__main__':
    app.run(debug=True)
