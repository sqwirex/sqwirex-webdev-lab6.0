import os
from datetime import datetime
from typing import Optional

from flask import url_for
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": 'ix_%(column_0_label)s',
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Flask-SQLAlchemy instance
DB = SQLAlchemy(model_class=Base)
db = DB


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)

    def __repr__(self):
        return f'<Category {self.name!r}>'


class User(Base, UserMixin):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    reviews: Mapped[list["Review"]] = relationship(back_populates='user', cascade='all, delete-orphan')
    courses: Mapped[list["Course"]] = relationship(back_populates='author')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return ' '.join(parts)

    def __repr__(self):
        return f'<User {self.login!r}>'


class Image(db.Model):
    __tablename__ = 'images'

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    md5_hash: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    object_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    object_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def storage_filename(self) -> str:
        _, ext = os.path.splitext(self.file_name)
        return self.id + ext

    @property
    def url(self) -> str:
        return url_for('image', image_id=self.id)

    def __repr__(self):
        return f'<Image {self.file_name!r}>'


class Course(Base):
    __tablename__ = 'courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_desc: Mapped[str] = mapped_column(Text, nullable=False)
    full_desc: Mapped[str] = mapped_column(Text, nullable=False)
    rating_sum: Mapped[int] = mapped_column(default=0)
    rating_num: Mapped[int] = mapped_column(default=0)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    background_image_id: Mapped[Optional[str]] = mapped_column(ForeignKey("images.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    author: Mapped["User"] = relationship(back_populates='courses')
    category: Mapped["Category"] = relationship(lazy=False)
    bg_image: Mapped[Optional["Image"]] = relationship()
    reviews: Mapped[list["Review"]] = relationship(
        back_populates='course',
        cascade='all, delete-orphan',
        order_by='desc(Review.created_at)',
    )

    @property
    def rating(self) -> float:
        if self.rating_num > 0:
            return self.rating_sum / self.rating_num
        return 0.0

    def recalculate_rating(self):
        self.rating_sum = sum(review.rating for review in self.reviews)
        self.rating_num = len(self.reviews)

    def __repr__(self):
        return f'<Course {self.name!r}>'


class Review(Base):
    __tablename__ = 'reviews'
    __table_args__ = (UniqueConstraint('course_id', 'user_id', name='uq_reviews_course_user'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)

    course: Mapped["Course"] = relationship(back_populates='reviews')
    user: Mapped["User"] = relationship(back_populates='reviews')

    def __repr__(self):
        return f'<Review course={self.course_id} user={self.user_id}>'
