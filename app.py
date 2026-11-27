"""
<YOUR PROJECT NAME> -- a Flask web app (team project starter).

Content comes from an external API (see api_client.py). The only data stored
is user accounts and their own data: systems, appliances... (see models.py). Authentication is
email + password with Flask sessions.

Run locally:   flask run --debug    ->   http://127.0.0.1:5000
"""
import os
from datetime import datetime, timedelta, timezone  # dates for the production log
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Lebanese time (Asia/Beirut)


from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort, g)  # g = per-request storage (Week 9: g.user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # IntegrityError = a broken unique rule; SQLAlchemyError = any database error

from models import db, User, Appliance, Plan, SolarSystem, ProductionLog, utc_now
import api_client
import solar  # our calculations (daily sunshine summary)
import sizing
from validators import (validate_signup, validate_login, validate_search, validate_system, 
                        validate_plan, validate_appliance, validate_log, SYSTEM_RANGES)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


EXAMPLE_KW = 3          # example system size: 3 kW, a typical Lebanese home system
EXAMPLE_TILT = 30       # panels tilted 30°, close to the best angle for Lebanon's latitude
EXAMPLE_AZIMUTH = 0     # 0 = facing south in Open-Meteo (-90 east, 90 west)


def system_production(lat, lon, panel_kw, tilt, azimuth):
    """Run one solar system through the solar functions: daily kWh, best day, best window."""
    forecast = api_client.get_forecast(lat, lon, tilt, azimuth)  # hourly irradiance on THIS system's tilted panels
    if forecast is None:  # None = the API failed (our api_client contract)
        return None  # the page shows an error message
    hourly = solar.hourly_kwh(forecast, panel_kw)  # kWh produced each hour by this system
    daily = solar.daily_kwh(hourly)  # total kWh per day
    best = solar.best_day(daily)  # the day with the most production (or None)
    window = solar.best_window(hourly, best["date"]) if best else None  # best 4 hours of that day
    return {"kw": panel_kw, "daily": daily, "best_day": best, "best_window": window}  # one dict for the template


def example_system(lat, lon):
    """The town page's fixed example: 3 kW, tilt 30°, facing south."""
    return system_production(lat, lon, EXAMPLE_KW, EXAMPLE_TILT, EXAMPLE_AZIMUTH)  # same code as a real system


def database_uri():
    """PostgreSQL on Render (DATABASE_URL), else a local SQLite file."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url
    return "sqlite:///" + os.path.abspath("app.db")


app.config["SQLALCHEMY_DATABASE_URI"] = database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
with app.app_context():
    db.create_all()


@app.context_processor
def inject_globals():
    """Make the logged-in user available in templates as current_user."""
    return {"current_user": g.get("user")}  # set by load_current_user (None if logged out); no second query


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request  # runs before EVERY request (Week 9: "Current user on each request")
def load_current_user():  # find who is logged in, once per request
    g.user = None  # default: nobody is logged in
    user_id = session.get("user_id")  # the id saved at log-in (None if not logged in)
    if user_id is not None:  # someone claims to be logged in
        user = db.session.get(User, user_id)  # load that user from the database
        if user is None:  # the account no longer exists (deleted)
            session.clear()  # end the session, so login_required sends them to /login
        else:  # the account exists
            g.user = user  # routes can use g.user instead of querying again


# ---------- content (from your API) --------------------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/search")  # GET /search?q=jounieh -> results page
def search():  # show the towns that match the search box
    errors, query = validate_search(request.args)  # check ?q=...; query = cleaned text, errors = {} if valid
    towns = []  # default: no towns to show
    api_failed = False  # becomes True if Open-Meteo is down or slow
    if not errors:  # only call the API when the input is valid
        result = api_client.search_towns(query)  # a list of towns, [] (no match) or None (API failed)
        if result is None:  # the API failed -> show "service unavailable"
            api_failed = True  # the template uses this to show the error message
        else:  # the API answered
            towns = result  # list of towns (may be empty)
    return render_template("results.html", query=query, towns=towns, errors=errors, api_failed=api_failed)  # send everything to the page


@app.route("/town/<int:place_id>")  # GET /town/273140; <int:...> makes Flask return 404 for /town/abc
def town(place_id):  # show one town and its 3-day sunshine forecast
    data = api_client.get_town(place_id)  # town dict, {} (no such town) or None (API failed)
    if data is None:  # Open-Meteo down or slow
        return render_template("town.html", town=None, api_failed=True), 503  # 503 = "service unavailable"
    if not data:  # {} -> bad id, unknown id, or a town outside Lebanon
        abort(404)  # standard "page not found"
    hours = api_client.get_town_forecast(data["lat"], data["lon"])  # hourly sunshine, [] (invalid) or None (API failed)
    forecast = solar.daily_sunshine(hours) if hours else []  # one summary per day; [] if no hours
    example = example_system(data["lat"], data["lon"])  # 3 kW example: daily kWh, best day, best window (None if API failed)
    return render_template("town.html", town=data, api_failed=False,  # show the town
        forecast=forecast, forecast_failed=hours is None,  # + forecast, or a "forecast unavailable" flag
        example=example)  # + the 3 kW example system (None if the API failed)

# ===================================================================
# AUTHENTICATION  --  YOU BUILD THIS (sign-up, log-in, log-out, sessions)
# ===================================================================
# This is YOUR work. The routes below are stubs. Implement them using what
# you learned in the "Sessions & Login" slides. Tools already imported for
# you at the top: generate_password_hash, check_password_hash, session,
# and the validators validate_signup / validate_login.
#
# What each route should do:
#   signup (POST): validate the form; reject an email that already exists;
#                  hash the password; create the User; store session["user_id"];
#                  redirect home.
#   login  (POST): validate; find the user by email; check_password_hash;
#                  on success store session["user_id"]; else show an error.
#   logout        : session.clear(); redirect home.
# The appliances and systems sections below show how the logged-in user is used.

# A real hash of a random password, made once at start-up. When an email does not exist,
# log-in still runs check_password_hash against this, so a missing account takes the same
# time as a wrong password (an attacker can't use the response time to find valid emails).
DUMMY_HASH = generate_password_hash(os.urandom(16).hex())  # nobody knows this password


@app.route("/signup", methods=["GET", "POST"])  # GET shows the form, POST creates the account
def signup():  # create a new account
    if request.method == "POST":  # the form was submitted
        errors, email = validate_signup(request.form)  # check every field on the server (never trust the browser)
        if not errors and User.query.filter_by(email=email).first():  # input is fine, but the email is taken
            errors["email"] = "This email can't be used. If it's yours, log in instead."  # no "already registered" detail
        if errors:  # something is wrong -> show the form again
            return render_template("signup.html", errors=errors,  # the messages under each field
                                   data={"email": email}), 400  # keep the email typed (never the password); 400 = bad input
        user = User(email=email,  # the new row, email already lower-case and trimmed
                    password_hash=generate_password_hash(request.form["password"]))  # store ONLY the hash
        db.session.add(user)  # stage the new user
        try:  # the commit can still fail if two sign-ups use the same email at the same moment
            db.session.commit()  # save -> user.id is created
        except IntegrityError:  # the unique rule on email blocked it
            db.session.rollback()  # undo the failed write (Week 10)
            errors["email"] = "This email can't be used. If it's yours, log in instead."  # same message as above
            return render_template("signup.html", errors=errors, data={"email": email}), 400  # show the form again
        session.clear()  # drop anything already in the session (against session fixation)
        session["user_id"] = user.id  # log the new user in: store only the small id
        flash("Welcome! Your account was created.")  # one-time message on the next page
        return redirect(url_for("welcome"))  # next step: the onboarding question
    return render_template("signup.html", errors={}, data={})  # GET: empty form


@app.route("/login", methods=["GET", "POST"])  # GET shows the form, POST checks the credentials
def login():  # start a session for an existing user
    if request.method == "POST":  # the form was submitted
        errors, email = validate_login(request.form)  # both fields filled in?
        if errors:  # an empty field -> show the form again
            return render_template("login.html", errors=errors, data={"email": email}), 400  # 400 = bad input
        password = request.form["password"]  # the typed password (only used for checking, never stored)
        user = User.query.filter_by(email=email).first()  # the account with this email, or None
        stored_hash = user.password_hash if user else DUMMY_HASH  # no account -> check against the dummy hash
        password_ok = check_password_hash(stored_hash, password)  # always runs, so both cases take the same time
        if user is None or not password_ok:  # wrong email OR wrong password
            app.logger.warning("Failed log-in for %r", email)  # %r escapes newlines (no fake log lines); never the password
            errors["form"] = "Email or password is incorrect."  # ONE message for both cases (Week 9)
            return render_template("login.html", errors=errors, data={"email": email}), 401  # 401 = not authenticated
        session.clear()  # new login -> brand-new session (against session fixation)
        session["user_id"] = user.id  # remember who is logged in
        flash("You are logged in.")  # one-time message
        if user.has_solar is None:  # never answered the onboarding question
            return redirect(url_for("welcome"))  # ask it now
        return redirect(url_for("home"))  # fixed destination (no ?next= -> no open redirect)
    return render_template("login.html", errors={}, data={})  # GET: empty form


@app.route("/logout", methods=["POST"])  # POST only: a link or <img> on another site can't log users out
def logout():  # end the session
    session.clear()  # remove everything, including user_id
    flash("You have been logged out.")  # one-time message
    return redirect(url_for("home"))  # back to the home page


@app.route("/welcome", methods=["GET", "POST"])  # onboarding: "Do you already have a solar system?"
@login_required  # only for logged-in users
def welcome():  # ask once, remember the answer in user.has_solar
    if request.method == "POST":  # one of the two buttons was clicked
        answer = request.form.get("has_solar", "")  # "yes", "no", or anything a tampered form sends
        if answer not in ("yes", "no"):  # only these two values are accepted
            flash("Please choose one of the two options.")  # explain the problem
            return render_template("welcome.html"), 400  # ask again; 400 = bad input
        g.user.has_solar = (answer == "yes")  # True = owner, False = future owner
        db.session.commit()  # save the answer
        if g.user.has_solar:  # already owns a system
            flash("Great! Search for your town, then add your system from the town page.")  # how to start
            return redirect(url_for("system_new"))  # the add-system page explains the steps
        flash("Let's plan your system: start by adding your appliances.")  # first step of the planner
        return redirect(url_for("appliances"))  # Christ's appliance pages (the planner's input)
    return render_template("welcome.html")  # GET: show the question


# ---------- solar systems (login required) ------------------------
MAX_SYSTEMS = 10  # limit per user, so one account can't fill the database with rows


def get_own_system(system_id):  # load a system and make sure it belongs to the logged-in user
    system = db.session.get(SolarSystem, system_id)  # the row with this id, or None
    if system is None:  # no system with this id
        abort(404)  # "page not found"
    if system.user_id != g.user.id:  # it exists, but belongs to someone else
        app.logger.warning("User %s was refused system %s", g.user.id, system_id)  # log it (Week 11)
        abort(403)  # "forbidden"
    return system  # safe to show or change


def check_town(place_id):  # validate a town id with Open-Meteo before saving it
    if place_id is None:  # missing or not a whole number
        return None, "Choose a town first: search for it, then use \"Add a system in this town\"."
    town = api_client.get_town(place_id)  # town dict, {} (unknown / outside Lebanon) or None (API failed)
    if town is None:  # Open-Meteo is down or slow
        return None, "We can't check the town right now. Please try again in a minute."
    if not town:  # {} -> not a valid Lebanese town
        return None, "This town is not valid. Please search for it again."
    return town, None  # the town's details, no error


@app.route("/systems")  # GET /systems -> my solar systems
@login_required  # only for logged-in users
def systems():  # list the logged-in user's systems
    my_systems = (SolarSystem.query  # only this user's rows (never all systems)
                  .filter_by(user_id=g.user.id)  # the ownership filter
                  .order_by(SolarSystem.name)  # alphabetical
                  .all())  # run the query -> list of SolarSystem objects
    towns = {}  # place_id -> town name, to show where each system is
    for place_id in {s.place_id for s in my_systems}:  # each different town once (the API answer is cached)
        town = api_client.get_town(place_id)  # town dict, {} or None
        towns[place_id] = town["name"] if town else None  # None -> the page shows "Town unavailable"
    return render_template("systems.html", systems=my_systems, towns=towns)  # show the list


@app.route("/systems/new", methods=["GET", "POST"])  # GET = form, POST = save
@login_required  # only for logged-in users
def system_new():  # add a solar system
    if request.method == "POST":  # the form was submitted
        place_id = request.form.get("place_id", type=int)  # hidden field; None if missing or not a number
    else:  # GET: the town comes from the link on the town page
        place_id = request.args.get("place_id", type=int)  # /systems/new?place_id=273140
    if place_id is None:  # no town chosen yet
        return render_template("system_form.html", system=None, town=None,  # explain how to choose a town
                               errors={}, form_data={})
    town, town_error = check_town(place_id)  # never trust the id: hidden fields and URLs can be edited
    if town_error:  # missing, unknown, or the API failed
        flash(town_error)  # explain the problem
        return render_template("system_form.html", system=None, town=None,  # back to the "choose a town" step
                               errors={}, form_data={}), 400  # 400 = bad request
    if request.method == "POST":  # town is valid -> check the other fields
        errors, values = validate_system(request.form)  # name + 4 numbers
        if not errors and len(g.user.systems) >= MAX_SYSTEMS:  # the user already has the maximum
            errors["form"] = f"You can have at most {MAX_SYSTEMS} systems."
        if errors:  # something is wrong -> show the form again with the messages
            return render_template("system_form.html", system=None, town=town,
                                   errors=errors, form_data=request.form), 400
        system = SolarSystem(user_id=g.user.id, place_id=place_id, **values)  # owner from the SESSION, never from the form
        g.user.has_solar = True  # whoever adds a system is now an owner
        db.session.add(system)  # stage the new row
        try:  # the database can still fail
            db.session.commit()  # save it
        except SQLAlchemyError:  # any database error
            db.session.rollback()  # undo, so the session is clean (Week 10)
            app.logger.exception("Could not save system")  # full error in the server log only
            flash("Could not save the system. Please try again.")  # simple message for the user
            return render_template("system_form.html", system=None, town=town,
                                   errors={}, form_data=request.form), 500
        flash("System added.")  # success message
        return redirect(url_for("system_detail", system_id=system.id))  # show the new system
    return render_template("system_form.html", system=None, town=town,  # GET with a valid town: empty form
                           errors={}, form_data={})


@app.route("/systems/<int:system_id>")  # GET /systems/5
@login_required  # only for logged-in users
def system_detail(system_id):  # one system's page (Chahine adds its forecast here)
    system = get_own_system(system_id)  # 404 if missing, 403 if not yours
    town = api_client.get_town(system.place_id)  # town dict, {} or None
    production = (system_production(town["lat"], town["lon"], system.panel_kw, system.tilt, system.azimuth)
                  if town else None)  # this system's 3-day forecast; None if the town or the API failed
    return render_template("system_detail.html", system=system, town=town or None,  # {} and None both -> "Town unavailable"
                           production=production)  # + the forecast for this system
@app.route("/systems/<int:system_id>/edit", methods=["GET", "POST"])  # GET = form, POST = save
@login_required  # only for logged-in users
def system_edit(system_id):  # change a system (its town stays the same)
    system = get_own_system(system_id)  # 404 if missing, 403 if not yours
    town = api_client.get_town(system.place_id) or None  # only to show the town name
    if request.method == "POST":  # the form was submitted
        errors, values = validate_system(request.form)  # name + 4 numbers (any place_id in the form is ignored)
        if errors:  # show the form again with the messages
            return render_template("system_form.html", system=system, town=town,
                                   errors=errors, form_data=request.form), 400
        for field, value in values.items():  # copy each cleaned value onto the row
            setattr(system, field, value)  # e.g. system.panel_kw = 3.5
        try:  # the database can still fail
            db.session.commit()  # save the changes
        except SQLAlchemyError:  # any database error
            db.session.rollback()  # undo
            app.logger.exception("Could not update system")  # details in the server log only
            flash("Could not update the system. Please try again.")
            return render_template("system_form.html", system=system, town=town,
                                   errors={}, form_data=request.form), 500
        flash("System updated.")  # success message
        return redirect(url_for("system_detail", system_id=system.id))  # back to the system page
    return render_template("system_form.html", system=system, town=town,  # GET: form filled with current values
                           errors={}, form_data={})


@app.route("/systems/<int:system_id>/delete", methods=["POST"])  # POST only: a link can't delete
@login_required  # only for logged-in users
def system_delete(system_id):  # delete a system and its production logs
    system = get_own_system(system_id)  # 404 if missing, 403 if not yours
    try:  # the database can fail
        db.session.delete(system)  # its ProductionLog rows go too (cascade in models.py)
        db.session.commit()  # save the deletion
    except SQLAlchemyError:  # any database error
        db.session.rollback()  # undo
        app.logger.exception("Could not delete system")  # details in the server log only
        flash("Could not delete the system. Please try again.")
    else:  # no error
        flash("System deleted.")
    return redirect(url_for("systems"))  # back to the list


# ===================================================================
#  SECTION -- appliances, planner (login required)
# ===================================================================
MAX_APPLIANCES = 50  # limit per user, so one account can't fill the database (A06: limits on counts)

# Typical Lebanese house loads, offered once so the user only has to edit them (proposal: "pre-filled").
TYPICAL_APPLIANCES = (  # (name, watts of one unit, quantity, hours by day, hours by night)
    ("Fridge", 150, 1, 12, 12),  # runs all the time (the compressor cycles on and off)
    ("LED lights", 10, 8, 2, 5),  # mostly in the evening
    ("TV", 100, 1, 3, 3),
    ("Internet router", 10, 1, 12, 12),  # on 24 hours
    ("Washing machine", 500, 1, 1, 0),  # best run in the sunny window
    ("Water pump", 750, 1, 0.5, 0),  # short daytime use
    ("Ceiling fan", 60, 2, 4, 4),
    ("Phone and laptop chargers", 65, 2, 2, 2),
)


def get_own_appliance(appliance_id):  # load an appliance and make sure it belongs to the logged-in user
    appliance = db.session.get(Appliance, appliance_id)  # the row with this id, or None
    if appliance is None:  # no appliance with this id
        abort(404)  # "page not found"
    if appliance.user_id != g.user.id:  # it exists, but belongs to someone else
        app.logger.warning("User %s was refused appliance %s", g.user.id, appliance_id)  # log it (A09)
        abort(403)  # "forbidden"
    return appliance  # safe to show or change


def my_appliances():  # the logged-in user's appliances, alphabetical
    return Appliance.query.filter_by(user_id=g.user.id).order_by(Appliance.name).all()  # ownership filter


@app.route("/appliances")  # GET /appliances -> my appliances
@login_required  # only for logged-in users
def appliances():  # list the user's appliances
    items = my_appliances()  # only this user's rows
    summary = sizing.load_summary(appliance_dicts(items)) if items else None  # live totals under the list
    return render_template("appliances.html", appliances=items, summary=summary)


@app.route("/appliances/new", methods=["GET", "POST"])  # GET = form, POST = save
@login_required
def appliance_new():  # add one appliance
    if request.method == "POST":  # the form was submitted
        errors, values = validate_appliance(request.form)  # check every field on the server
        if not errors and len(g.user.appliances) >= MAX_APPLIANCES:  # already at the limit
            errors["form"] = f"You can have at most {MAX_APPLIANCES} appliances."
        if errors:  # show the form again with a message under each wrong field
            return render_template("appliance_form.html", appliance=None,
                                   errors=errors, form_data=request.form), 400  # 400 = bad input
        db.session.add(Appliance(user_id=g.user.id, **values))  # owner from the SESSION, never from the form
        try:  # the database can still fail
            db.session.commit()  # save it
        except SQLAlchemyError:  # any database error
            db.session.rollback()  # undo, so the session stays usable (Week 10)
            app.logger.exception("Could not save appliance")  # details in the server log only
            flash("Could not save the appliance. Please try again.", "error")
            return render_template("appliance_form.html", appliance=None,
                                   errors={}, form_data=request.form), 500
        flash("Appliance added.", "success")
        return redirect(url_for("appliances"))  # Post/Redirect/Get: refresh won't add it twice
    return render_template("appliance_form.html", appliance=None, errors={}, form_data={})  # GET: empty form


@app.route("/appliances/typical", methods=["POST"])  # POST only: it writes to the database
@login_required
def appliance_typical():  # add the typical Lebanese appliances in one click (only when the list is empty)
    if g.user.appliances:  # already has appliances -> don't add duplicates
        flash("You already have appliances. Edit them or add new ones one by one.", "error")
        return redirect(url_for("appliances"))
    for name, power_w, quantity, hours_day, hours_night in TYPICAL_APPLIANCES:  # one row per typical load
        db.session.add(Appliance(user_id=g.user.id, name=name, power_w=power_w, quantity=quantity,
                                 hours_day=hours_day, hours_night=hours_night))
    try:
        db.session.commit()  # all rows saved together (one transaction)
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not add typical appliances")
        flash("Could not add the appliances. Please try again.", "error")
    else:
        flash("Typical appliances added. Edit them so they match your house.", "success")
    return redirect(url_for("appliances"))


@app.route("/appliances/<int:appliance_id>/edit", methods=["GET", "POST"])
@login_required
def appliance_edit(appliance_id):  # change one appliance
    appliance = get_own_appliance(appliance_id)  # 404 if missing, 403 if not yours
    if request.method == "POST":
        errors, values = validate_appliance(request.form)
        if errors:
            return render_template("appliance_form.html", appliance=appliance,
                                   errors=errors, form_data=request.form), 400
        for field, value in values.items():  # copy each cleaned value onto the row
            setattr(appliance, field, value)  # e.g. appliance.power_w = 150
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Could not update appliance")
            flash("Could not update the appliance. Please try again.", "error")
            return render_template("appliance_form.html", appliance=appliance,
                                   errors={}, form_data=request.form), 500
        flash("Appliance updated.", "success")
        return redirect(url_for("appliances"))
    return render_template("appliance_form.html", appliance=appliance, errors={}, form_data={})  # GET: filled form


@app.route("/appliances/<int:appliance_id>/delete", methods=["POST"])  # POST only: a link can't delete
@login_required
def appliance_delete(appliance_id):
    appliance = get_own_appliance(appliance_id)  # 404 / 403 checks
    try:
        db.session.delete(appliance)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not delete appliance")
        flash("Could not delete the appliance. Please try again.", "error")
    else:
        flash("Appliance deleted.", "success")
    return redirect(url_for("appliances"))


# ---------- planner ------------------------------------------------
PLANNED_SYSTEM_NAME = "My planned system"  # name given to the system created by "I installed it"


def appliance_dicts(items):  # Appliance rows -> the plain dicts sizing.load_summary expects
    return [{"power_w": a.power_w, "quantity": a.quantity,
             "hours_day": a.hours_day, "hours_night": a.hours_night} for a in items]


def latest_plan():  # the logged-in user's most recent plan, or None
    return (Plan.query.filter_by(user_id=g.user.id)  # ownership filter
            .order_by(Plan.created_at.desc(), Plan.id.desc()).first())  # newest first


def compute_plan(plan, items):  # the planner maths for one plan, used by the result page AND by install
    """Return (town, summary, result, error). error is a message when the town can't be used."""
    town = api_client.get_town(plan.place_id)  # dict, {} (invalid) or None (API failed)
    if town is None:  # Open-Meteo down or slow
        return None, None, None, "The weather service is not responding. Please try again in a minute."
    if not town:  # the saved id is no longer a valid Lebanese town
        return None, None, None, "This plan's town is not valid any more. Choose your town again."
    summary = sizing.load_summary(appliance_dicts(items))  # daily, night and peak load
    psh = api_client.get_winter_sun_hours(town["lat"], town["lon"])  # always a number (fallback inside)
    result = sizing.suggest_system(e_day=summary["e_day"], e_night=summary["e_night"],
                                   peak_kw=summary["peak_kw"], psh_winter=psh,
                                   autonomy_days=plan.autonomy_days, has_grid=plan.has_grid,
                                   panel_w=plan.panel_w)  # server recomputes (A06); names = no order mistakes
    return town, summary, result, None


def can_save_as_system(result):  # can "I installed this" save the suggestion as a normal system?
    """True only if the suggestion fits the same limits as Elia's system form, so the owner can edit it later."""
    low_kw, high_kw, _ = SYSTEM_RANGES["panel_kw"]  # 0.1 .. 50 kW
    _, high_kwh, _ = SYSTEM_RANGES["battery_kwh"]  # .. 100 kWh
    return (result["inverter_kw"] is not None  # above 12 kW we don't suggest one standard inverter
            and low_kw <= result["installed_kwp"] <= high_kw  # e.g. 80 kW or 0 kW is refused
            and result["battery_kwh"] <= high_kwh)


@app.route("/api/towns")  # GET /api/towns?q=jou -> JSON list for the planner's town search box
@login_required  # only the planner uses it
def api_towns():
    errors, query = validate_search(request.args)  # same rules as /search (2-60 characters, allowed letters)
    if errors:  # invalid input -> no API call
        return {"error": errors["q"], "towns": []}, 400  # Flask turns a dict into JSON
    towns = api_client.search_towns(query)  # list, [] or None
    if towns is None:  # Open-Meteo failed
        return {"error": "The weather service is not responding. Please try again.", "towns": []}, 503
    return {"towns": [{"id": t["id"], "name": t["name"], "region": t["region"] or "Lebanon"}
                      for t in towns]}  # only the fields the page needs


@app.route("/planner", methods=["GET", "POST"])  # GET = form, POST = save the inputs
@login_required
def planner():
    items = my_appliances()  # the planner's input
    if not items:  # nothing to size yet
        flash("Add your appliances before creating a solar plan.", "error")
        return redirect(url_for("appliances"))
    plan = latest_plan()  # the plan we update (one plan per user, so the table doesn't grow forever)
    if request.method == "POST":
        errors, values = validate_plan(request.form)  # check every field
        if not errors:  # the id is a whole number -> does the town exist and is it in Lebanon?
            town = api_client.get_town(values["place_id"])
            if town is None:  # API down
                flash("The weather service is not responding. Please try again.", "error")
                return render_template("planner.html", appliances=items,
                                       plan_data=request.form, errors={}), 503
            if not town:  # {} -> unknown id or outside Lebanon
                errors["place_id"] = "Choose your town from the suggestions."
        if errors:
            return render_template("planner.html", appliances=items,
                                   plan_data=request.form, errors=errors), 400
        if plan is None:  # first plan for this user
            plan = Plan(user_id=g.user.id)  # owner from the session
            db.session.add(plan)
        for field, value in values.items():  # copy the cleaned inputs onto the row
            setattr(plan, field, value)
        plan.created_at = utc_now()  # "saved at" = now, so the newest plan is always this one
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Could not save planner inputs")
            flash("Could not save your plan. Please try again.", "error")
            return render_template("planner.html", appliances=items,
                                   plan_data=request.form, errors={}), 500
        return redirect(url_for("planner_result"))  # results are recomputed there, never stored
    plan_data = {"place_id": "", "town_name": "", "autonomy_days": "1", "has_grid": "yes", "panel_w": "550"}  # defaults
    if plan:  # show the previous inputs again
        town = api_client.get_town(plan.place_id) or {}  # only to show the town's name in the box
        plan_data = {"place_id": plan.place_id if town else "", "town_name": town.get("name", ""),
                     "autonomy_days": str(plan.autonomy_days), "has_grid": "yes" if plan.has_grid else "no",
                     "panel_w": str(plan.panel_w)}  # strings, like request.form, so the template compares one way
    return render_template("planner.html", appliances=items, plan_data=plan_data, errors={})


@app.route("/planner/result")  # GET: load calculation + suggested system
@login_required
def planner_result():
    plan = latest_plan()
    if plan is None:
        flash("Fill in the planner first.", "error")
        return redirect(url_for("planner"))
    items = my_appliances()
    if not items:
        flash("Add your appliances before viewing a plan.", "error")
        return redirect(url_for("appliances"))
    town, summary, result, error = compute_plan(plan, items)  # same code as install
    can_install = not error and can_save_as_system(result)  # hide the install button when it would be refused
    return render_template("planner_result.html", plan=plan, town=town, appliances=items,
                           summary=summary, result=result, error=error,
                           can_install=can_install), (503 if error else 200)


@app.route("/planner/install", methods=["POST"])  # "I installed this -> save as my system"
@login_required
def planner_install():
    plan = latest_plan()
    items = my_appliances()
    if plan is None or not items:
        flash("Fill in the planner first.", "error")
        return redirect(url_for("planner"))
    town, summary, result, error = compute_plan(plan, items)  # recompute: never trust numbers from the browser
    if error:
        flash(error, "error")
        return redirect(url_for("planner_result"))
    if not can_save_as_system(result):  # over 12 kW inverter, panels outside 0.1-50 kW, or battery over 100 kWh
        flash("This system is outside what we can save (inverter up to 12 kW, 0.1 to 50 kW of panels, "
              "battery up to 100 kWh). Please ask a certified installer.", "error")
        return redirect(url_for("planner_result"))
    existing = SolarSystem.query.filter_by(user_id=g.user.id, name=PLANNED_SYSTEM_NAME,
                                           place_id=plan.place_id,
                                           panel_kw=result["installed_kwp"]).first()  # same plan already saved?
    if existing:  # double click or second visit -> don't create a copy
        flash("This planned system is already in your systems.", "success")
        return redirect(url_for("system_detail", system_id=existing.id))
    if len(g.user.systems) >= MAX_SYSTEMS:  # same limit as Elia's "Add a system"
        flash(f"You can have at most {MAX_SYSTEMS} systems.", "error")
        return redirect(url_for("systems"))
    system = SolarSystem(user_id=g.user.id, place_id=plan.place_id, name=PLANNED_SYSTEM_NAME,
                         panel_kw=result["installed_kwp"], battery_kwh=result["battery_kwh"],
                         tilt=30, azimuth=0)  # 30° facing south: the usual Lebanese installation (editable later)
    db.session.add(system)
    g.user.has_solar = True  # the user now owns a system
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not save planned system")
        flash("Could not save your solar system. Please try again.", "error")
        return redirect(url_for("planner_result"))
    flash("Your solar system was added. Edit its tilt and direction if they differ.", "success")
    return redirect(url_for("system_detail", system_id=system.id))  # straight to its forecast

# ---------- production log  --------------------------------
UNDERPERFORM_RATIO = 0.75  # under 75% of the estimate = "check or clean the panels" (project plan)
LOG_PAGE_SIZE = 60  # show the latest 60 readings


def lebanon_today():  # today's date in Beirut (the server on Render runs in UTC)
    try:
        return datetime.now(ZoneInfo("Asia/Beirut")).date()  # handles summer time automatically
    except ZoneInfoNotFoundError:  # no time-zone data on the machine (fixed by tzdata in requirements)
        return (datetime.now(timezone.utc) + timedelta(hours=2)).date()  # Lebanon winter time as a fallback


def estimates_by_date(system, town):  # {"2026-11-20": 12.3, ...} for the last 7 days and the next 3
    """Estimated kWh per day from the same forecast maths as the system page; {} if the API failed."""
    if not town:  # unknown town or API down
        return {}
    forecast = api_client.get_forecast(town["lat"], town["lon"], system.tilt, system.azimuth, past_days=7)
    if not forecast:  # None (API failed) or [] (invalid inputs)
        return {}
    daily = solar.daily_kwh(solar.hourly_kwh(forecast, system.panel_kw))  # same formula as the forecast page
    return {day["date"]: day["kwh"] for day in daily}


def get_own_log(log_id):  # a reading belongs to the user through its system
    log = db.session.get(ProductionLog, log_id)
    if log is None:
        abort(404)
    if log.system.user_id != g.user.id:  # log -> system -> owner
        app.logger.warning("User %s was refused log %s", g.user.id, log_id)
        abort(403)
    return log


@app.route("/systems/<int:system_id>/logs", methods=["GET", "POST"])  # GET = list, POST = add a reading
@login_required
def system_logs(system_id):
    system = get_own_system(system_id)  # Elia's helper: 404 / 403
    today = lebanon_today()
    errors, form_data, status = {}, {}, 200
    if request.method == "POST":
        errors, values = validate_log(request.form, today)
        form_data = request.form  # show what was typed if there is an error
        if not errors:
            db.session.add(ProductionLog(system_id=system.id, **values))  # system id from the URL (already owner-checked)
            try:
                db.session.commit()
            except IntegrityError:  # UNIQUE(system_id, date): this day already has a reading
                db.session.rollback()  # Week 10: undo the failed write
                errors["date"] = "You already logged this day. Delete the old reading first."
            except SQLAlchemyError:
                db.session.rollback()
                app.logger.exception("Could not save production log")
                errors["form"] = "Could not save the reading. Please try again."
            else:
                flash("Reading saved.", "success")
                return redirect(url_for("system_logs", system_id=system.id))  # Post/Redirect/Get
        status = 400 if errors else 200
    town = api_client.get_town(system.place_id) or None  # only to name the town and get coordinates
    estimates = estimates_by_date(system, town)  # {} if the API failed -> "no estimate" in the table
    logs = (ProductionLog.query.filter_by(system_id=system.id)
            .order_by(ProductionLog.date.desc()).limit(LOG_PAGE_SIZE).all())  # newest first
    rows = []  # one row per reading, with the estimate and accuracy when we have one
    for log in logs:
        estimate = estimates.get(log.date.isoformat())  # None for days older than 7 days
        accuracy = round(log.actual_kwh / estimate * 100) if estimate else None  # % of the estimate
        rows.append({"log": log, "estimate": estimate, "accuracy": accuracy,
                     "low": accuracy is not None and accuracy < UNDERPERFORM_RATIO * 100})
    compared = [r["accuracy"] for r in rows if r["accuracy"] is not None]  # readings we could compare
    average = round(sum(compared) / len(compared)) if compared else None  # average accuracy
    return render_template("system_logs.html", system=system, town=town, rows=rows, average=average,
                           errors=errors, form_data=form_data, today=today.isoformat(),
                           api_failed=bool(town) and not estimates,
                           low_limit=round(UNDERPERFORM_RATIO * 100)), status


@app.route("/logs/<int:log_id>/delete", methods=["POST"])
@login_required
def log_delete(log_id):
    log = get_own_log(log_id)  # 404 / 403 through the system's owner
    system_id = log.system_id  # remember where to go back
    try:
        db.session.delete(log)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not delete production log")
        flash("Could not delete the reading. Please try again.", "error")
    else:
        flash("Reading deleted.", "success")
    return redirect(url_for("system_logs", system_id=system_id))

if __name__ == "__main__":
    app.run(debug=True)