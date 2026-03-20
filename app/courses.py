from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

try:
    from .models import Category, Course, Review, User, db
    from .tools import CoursesFilter, ImageSaver
except ImportError:
    from models import Category, Course, Review, User, db
    from tools import CoursesFilter, ImageSaver

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = ['author_id', 'name', 'category_id', 'short_desc', 'full_desc']
RATING_CHOICES = [
    (5, 'отлично'),
    (4, 'хорошо'),
    (3, 'удовлетворительно'),
    (2, 'неудовлетворительно'),
    (1, 'плохо'),
    (0, 'ужасно'),
]
SORT_OPTIONS = {
    'new': ('По новизне', [Review.created_at.desc()]),
    'positive': ('Сначала положительные', [Review.rating.desc(), Review.created_at.desc()]),
    'negative': ('Сначала отрицательные', [Review.rating.asc(), Review.created_at.desc()]),
}


def params():
    return {p: request.form.get(p) or None for p in COURSE_PARAMS}


def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }


def get_sort_value():
    sort = request.args.get('sort', 'new')
    return sort if sort in SORT_OPTIONS else 'new'


def build_reviews_query(course_id: int, sort_value: str):
    query = db.select(Review).filter(Review.course_id == course_id)
    for criterion in SORT_OPTIONS[sort_value][1]:
        query = query.order_by(criterion)
    return query


def current_user_review(course_id: int):
    if not current_user.is_authenticated:
        return None
    return db.session.execute(
        db.select(Review).filter_by(course_id=course_id, user_id=current_user.id)
    ).scalar()


@bp.route('/')
def index():
    courses_query = CoursesFilter(**search_params()).perform()
    pagination = db.paginate(courses_query, per_page=6)
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template(
        'courses/index.html',
        courses=pagination.items,
        categories=categories,
        pagination=pagination,
        search_params=search_params(),
    )


@bp.route('/new')
@login_required
def new():
    course = Course(author_id=current_user.id)
    categories = db.session.execute(db.select(Category)).scalars()
    users = db.session.execute(db.select(User)).scalars()
    return render_template('courses/new.html', categories=categories, users=users, course=course)


@bp.route('/create', methods=['POST'])
@login_required
def create():

    f = request.files.get('background_img')
    img = None
    course = Course()
    try:
        if f and f.filename:
            img = ImageSaver(f).save()

        image_id = img.id if img else None
        course = Course(**params(), background_image_id=image_id)
        db.session.add(course)
        db.session.commit()
    except IntegrityError as err:
        flash(
            f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})',
            'danger',
        )
        db.session.rollback()
        categories = db.session.execute(db.select(Category)).scalars()
        users = db.session.execute(db.select(User)).scalars()
        return render_template('courses/new.html', categories=categories, users=users, course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')
    return redirect(url_for('courses.index'))


@bp.route('/<int:course_id>')
def show(course_id):
    course = db.get_or_404(Course, course_id)
    latest_reviews = db.session.execute(
        db.select(Review).filter(Review.course_id == course_id).order_by(Review.created_at.desc()).limit(5)
    ).scalars()
    user_review = current_user_review(course_id)
    return render_template(
        'courses/show.html',
        course=course,
        latest_reviews=latest_reviews,
        user_review=user_review,
        rating_choices=RATING_CHOICES,
    )


@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = db.get_or_404(Course, course_id)
    sort_value = get_sort_value()
    pagination = db.paginate(build_reviews_query(course_id, sort_value), per_page=5)
    user_review = current_user_review(course_id)
    return render_template(
        'courses/reviews.html',
        course=course,
        reviews=pagination.items,
        pagination=pagination,
        sort_value=sort_value,
        sort_options=SORT_OPTIONS,
        user_review=user_review,
        rating_choices=RATING_CHOICES,
    )


@bp.route('/<int:course_id>/reviews/create', methods=['POST'])
@login_required
def create_review(course_id):
    course = db.get_or_404(Course, course_id)
    rating_raw = request.form.get('rating', '5')
    text = (request.form.get('text') or '').strip()
    next_endpoint = request.form.get('next_endpoint', 'courses.show')
    sort_value = request.form.get('sort', 'new')

    existing = current_user_review(course_id)
    if existing:
        flash('Вы уже оставили отзыв к этому курсу.', 'warning')
        if next_endpoint == 'courses.reviews':
            return redirect(url_for('courses.reviews', course_id=course_id, sort=sort_value))
        return redirect(url_for('courses.show', course_id=course_id))

    try:
        rating = int(rating_raw)
    except ValueError:
        rating = -1

    if rating not in range(0, 6) or not text:
        flash('Не удалось сохранить отзыв. Проверьте оценку и текст.', 'danger')
        if next_endpoint == 'courses.reviews':
            return redirect(url_for('courses.reviews', course_id=course_id, sort=sort_value))
        return redirect(url_for('courses.show', course_id=course_id))

    review = Review(rating=rating, text=text, course_id=course.id, user_id=current_user.id)
    db.session.add(review)
    db.session.flush()
    course.recalculate_rating()

    try:
        db.session.commit()
        flash('Ваш отзыв успешно сохранён.', 'success')
    except IntegrityError as err:
        db.session.rollback()
        flash(f'Возникла ошибка при сохранении отзыва. ({err})', 'danger')

    if next_endpoint == 'courses.reviews':
        return redirect(url_for('courses.reviews', course_id=course_id, sort=sort_value))
    return redirect(url_for('courses.show', course_id=course_id))
