"""
reset_db.py  --  (re)create the database tables for LOCAL development.

Run it whenever you change your models in models.py:
    python reset_db.py

WARNING: it drops all tables first, so you lose any local data. That's fine
during development. On Render, the app creates the tables automatically when
it starts (db.create_all() in app.py) - you do NOT run this script there.
To change the schema on Render after it exists, drop the table in the
database's PSQL console, then restart the service.
"""
from app import app
from models import db

with app.app_context():
    db.drop_all()
    db.create_all()
    print("Database reset: all tables created from models.py.")
