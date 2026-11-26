"""
models.py  --  the internal database: every table SolarSmart stores (Elia).

We store ONLY user accounts and each user's own data. Town names, coordinates
and forecasts are never stored: we keep the Open-Meteo place_id and fetch the
rest live through api_client.py (course rule).

After changing this file locally, run:  python reset_db.py
"""
from datetime import datetime, timezone  # tools to create the current date and time

from flask_sqlalchemy import SQLAlchemy  # the ORM: Python classes <-> database tables (Week 10)

db = SQLAlchemy()  # the one database handle, connected to the app in app.py (db.init_app)


def utc_now():  # the default value for every "created at / checked at" column
    """Current time in UTC, without timezone info (same behaviour on SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)  # take UTC time, then drop the "+00:00" label


# ---------------------------------------------------------------------------
# User -- one row per account (login + preferences)
# ---------------------------------------------------------------------------
class User(db.Model):  # table "user"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each user, created automatically
    email = db.Column(db.String(255), unique=True, nullable=False)  # login name; unique = no two accounts with the same email
    password_hash = db.Column(db.String(255), nullable=False)  # ONLY the Werkzeug hash, never the real password
    has_solar = db.Column(db.Boolean, nullable=True, default=None)  # None = not asked yet, True = owner, False = future owner
    notify_weather = db.Column(db.Boolean, nullable=False, default=True)  # wants sunny/cloudy/best-day notifications (on by default)
    notify_performance = db.Column(db.Boolean, nullable=False, default=True)  # wants under-performance/log reminders (on by default)
    last_checked_at = db.Column(db.DateTime, nullable=True)  # last time the notification check ran (None = never)

    systems = db.relationship("SolarSystem", backref="user",  # user.systems = their solar systems; system.user = the owner
                              cascade="all, delete-orphan")  # deleting a user deletes their systems
    appliances = db.relationship("Appliance", backref="user",  # user.appliances = their house appliances
                                 cascade="all, delete-orphan")  # deleting a user deletes their appliances
    plans = db.relationship("Plan", backref="user",  # user.plans = their saved planner inputs
                            cascade="all, delete-orphan")  # deleting a user deletes their plans
    notifications = db.relationship("Notification", backref="user",  # user.notifications = their notifications
                                    cascade="all, delete-orphan")  # deleting a user deletes their notifications


# ---------------------------------------------------------------------------
# SolarSystem -- a system a user already owns (replaced the starter's Favorite)
# ---------------------------------------------------------------------------
class SolarSystem(db.Model):  # table "solar_system"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each system (used in /systems/<id>)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # owner: used by the ownership check (403)
    place_id = db.Column(db.Integer, nullable=False)  # Open-Meteo town id (e.g. 273140); NOT a foreign key, checked with get_town()
    name = db.Column(db.String(40), nullable=False)  # user's label, e.g. "Home roof" (validator: 1-40 characters)
    panel_kw = db.Column(db.Float, nullable=False)  # total panel power in kW (validator: 0.1-50)
    tilt = db.Column(db.Float, nullable=False)  # panel angle in degrees, 0 = flat, 90 = vertical (validator: 0-90)
    azimuth = db.Column(db.Float, nullable=False)  # direction in degrees, 0 = south, -90 = east, 90 = west (validator: -180 to 180)
    battery_kwh = db.Column(db.Float, nullable=False, default=0.0)  # battery capacity in kWh, 0 = no battery (validator: 0-100)

    logs = db.relationship("ProductionLog", backref="system",  # system.logs = its readings; log.system = the system
                           cascade="all, delete-orphan")  # deleting a system deletes its readings


# ---------------------------------------------------------------------------
# Appliance -- one house appliance (used by the planner and the schedule)
# ---------------------------------------------------------------------------
class Appliance(db.Model):  # table "appliance"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each appliance
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # owner: used by the ownership check (403)
    name = db.Column(db.String(40), nullable=False)  # e.g. "Fridge" (validator: 1-40 characters)
    power_w = db.Column(db.Integer, nullable=False)  # power of ONE unit in watts (validator: 1-10000)
    quantity = db.Column(db.Integer, nullable=False, default=1)  # how many of them (validator: 1-50)
    hours_day = db.Column(db.Float, nullable=False, default=0.0)  # hours used during daylight (validator: 0-24)
    hours_night = db.Column(db.Float, nullable=False, default=0.0)  # hours used at night (validator: 0-24, day + night <= 24)


# ---------------------------------------------------------------------------
# Plan -- the planner's INPUTS; results are recomputed by sizing.py (never stored)
# ---------------------------------------------------------------------------
class Plan(db.Model):  # table "plan"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each plan
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # owner: used by the ownership check (403)
    place_id = db.Column(db.Integer, nullable=False)  # Open-Meteo town id (gives the winter sun hours)
    panel_w = db.Column(db.Integer, nullable=False, default=550)  # watts of one panel model (validator: 100-800)
    autonomy_days = db.Column(db.Integer, nullable=False, default=1)  # days the battery must last (validator: 0-3)
    has_grid = db.Column(db.Boolean, nullable=False, default=False)  # EDL or generator present: True = hybrid, False = off-grid
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)  # when the plan was saved (UTC); utc_now without () = called per row


# ---------------------------------------------------------------------------
# ProductionLog -- one real reading per system per day
# ---------------------------------------------------------------------------
class ProductionLog(db.Model):  # table "production_log"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each reading
    system_id = db.Column(db.Integer, db.ForeignKey("solar_system.id"), nullable=False)  # which system; ownership = log.system.user_id
    date = db.Column(db.Date, nullable=False)  # the day of the reading (date only, no time; validator: not in the future)
    actual_kwh = db.Column(db.Float, nullable=False)  # energy the inverter measured that day (validator: 0-500)
    __table_args__ = (db.UniqueConstraint("system_id", "date",  # only one reading per system per day
                                          name="uniq_system_date"),)  # a duplicate raises IntegrityError -> rollback


# ---------------------------------------------------------------------------
# Notification -- one in-app message for one user
# ---------------------------------------------------------------------------
class Notification(db.Model):  # table "notification"
    id = db.Column(db.Integer, primary_key=True)  # unique number for each notification
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # owner: used by the ownership check (403)
    type = db.Column(db.String(20), nullable=False)  # event kind: sunny_day, cloudy_day, best_day, underperform, log_reminder, plan_ready
    message = db.Column(db.String(255), nullable=False)  # text shown to the user (printed with {{ }}, auto-escaped)
    link = db.Column(db.String(255), nullable=True)  # optional page to open, e.g. "/systems/5" (a local path we build, never user input)
    event_key = db.Column(db.String(100), nullable=False)  # identifies the event, e.g. "sunny:2026-11-15:system5"
    is_read = db.Column(db.Boolean, nullable=False, default=False)  # False = unread (counted in the bell)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)  # when it was created (UTC)
    __table_args__ = (db.UniqueConstraint("user_id", "event_key",  # the same event is never stored twice for a user
                                          name="uniq_user_event"),)  # a duplicate raises IntegrityError -> rollback