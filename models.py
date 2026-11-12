"""Database models. The only data your app stores: user accounts and favorites.
You may add fields to Favorite to match your topic (e.g. a price, a year)."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    favorites = db.relationship("Favorite", backref="user",
                                cascade="all, delete-orphan")


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_id = db.Column(db.String(50), nullable=False)     # the API's id for the item
    item_title = db.Column(db.String(255))
    item_image = db.Column(db.String(500))
    __table_args__ = (db.UniqueConstraint("user_id", "item_id",
                                          name="uniq_user_item"),)
