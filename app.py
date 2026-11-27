"""
<YOUR PROJECT NAME> -- a Flask web app (team project starter).

Content comes from an external API (see api_client.py). The only data stored
is user accounts and their own data: systems, appliances... (see models.py). Authentication is
email + password with Flask sessions.

Run locally:   flask run --debug    ->   http://127.0.0.1:5000
"""
import os
from functools import wraps
from datetime import datetime  # to read the current date and time
from zoneinfo import ZoneInfo  # time zones (Asia/Beirut); tzdata provides the data on Windows

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort, g)  # g = per-request storage (Week 9: g.user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # IntegrityError = a broken unique rule; SQLAlchemyError = any database error

from models import db, User, Appliance, Plan, SolarSystem
import api_client
import solar  # our calculations (daily sunshine summary)
import sizing
from validators import validate_signup, validate_login, validate_search,validate_system, validate_plan

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


EXAMPLE_KW = 3          # example system size: 3 kW, a typical Lebanese home system
EXAMPLE_TILT = 30       # panels tilted 30°, close to the best angle for Lebanon's latitude
EXAMPLE_AZIMUTH = 0     # 0 = facing south in Open-Meteo (-90 east, 90 west)
LEBANON = ZoneInfo("Asia/Beirut")  # Open-Meteo times are in Lebanese time, so "now" must be too

def system_production(lat, lon, panel_kw, tilt, azimuth):
    """Run one solar system through the solar functions: daily kWh, best day, best window."""
    forecast = api_client.get_forecast(lat, lon, tilt, azimuth)  # hourly irradiance on THIS system's tilted panels
    if forecast is None:  # None = the API failed (our api_client contract)
        return None  # the page shows an error message
    hourly = solar.hourly_kwh(forecast, panel_kw)  # kWh produced each hour by this system
    daily = solar.daily_kwh(hourly)  # total kWh per day
    best = solar.best_day(daily)  # the day with the most production (or None)
    now = datetime.now(LEBANON).strftime("%Y-%m-%dT%H:%M")  # current Lebanese time, same format as the API's times
    window = solar.next_best_window(hourly, now)  # best 4 hours that haven't finished yet (today or later)
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


# ---------- appliances (login required) ---------------------------

def validate_appliance_form(form):
    """Validate and clean appliance fields from a submitted form."""
    name = form.get("name", "").strip()

    try:
        power_w = int(form.get("power_w", ""))
        quantity = int(form.get("quantity", ""))
        hours_day = float(form.get("hours_day", ""))
        hours_night = float(form.get("hours_night", ""))
    except (TypeError, ValueError):
        return None, "Enter valid numbers for power, quantity, and hours."

    if not 1 <= len(name) <= 40:
        return None, "Name must be between 1 and 40 characters."
    if not 1 <= power_w <= 10000:
        return None, "Power must be between 1 and 10,000 W."
    if not 1 <= quantity <= 50:
        return None, "Quantity must be between 1 and 50."
    if not 0 <= hours_day <= 24 or not 0 <= hours_night <= 24:
        return None, "Each hours value must be between 0 and 24."
    if hours_day + hours_night > 24:
        return None, "Day and night hours cannot add up to more than 24."

    return {
        "name": name,
        "power_w": power_w,
        "quantity": quantity,
        "hours_day": hours_day,
        "hours_night": hours_night,
    }, None


@app.route("/appliances")
@login_required
def appliances():
    items = (
        Appliance.query
        .filter_by(user_id=session["user_id"])
        .order_by(Appliance.name)
        .all()
    )
    return render_template("appliances.html", appliances=items)


@app.route("/appliances/new", methods=["GET", "POST"])
@login_required
def appliance_new():
    if request.method == "POST":
        values, error = validate_appliance_form(request.form)

        if error:
            flash(error, "error")
            return render_template(
                "appliance_form.html", appliance=None, form_data=request.form
            ), 400

        appliance = Appliance(user_id=session["user_id"], **values)
        db.session.add(appliance)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not save appliance")
            flash("Could not save the appliance. Please try again.", "error")
            return render_template(
                "appliance_form.html", appliance=None, form_data=request.form
            ), 500

        flash("Appliance added.", "success")
        return redirect(url_for("appliances"))

    return render_template(
        "appliance_form.html", appliance=None, form_data={}
    )


@app.route("/appliances/<int:appliance_id>/edit", methods=["GET", "POST"])
@login_required
def appliance_edit(appliance_id):
    appliance = db.session.get(Appliance, appliance_id)

    if appliance is None:
        abort(404)
    if appliance.user_id != session["user_id"]:
        abort(403)

    if request.method == "POST":
        values, error = validate_appliance_form(request.form)

        if error:
            flash(error, "error")
            return render_template(
                "appliance_form.html", appliance=appliance, form_data=request.form
            ), 400

        for field, value in values.items():
            setattr(appliance, field, value)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not update appliance")
            flash("Could not update the appliance. Please try again.", "error")
            return render_template(
                "appliance_form.html", appliance=appliance, form_data=request.form
            ), 500

        flash("Appliance updated.", "success")
        return redirect(url_for("appliances"))

    return render_template(
        "appliance_form.html", appliance=appliance, form_data={}
    )


@app.route("/appliances/<int:appliance_id>/delete", methods=["POST"])
@login_required
def appliance_delete(appliance_id):
    appliance = db.session.get(Appliance, appliance_id)

    if appliance is None:
        abort(404)
    if appliance.user_id != session["user_id"]:
        abort(403)

    try:
        db.session.delete(appliance)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Could not delete appliance")
        flash("Could not delete the appliance. Please try again.", "error")
    else:
        flash("Appliance deleted.", "success")

    return redirect(url_for("appliances"))



@app.route("/planner", methods=["GET", "POST"])
@login_required
def planner():
    user_id = session["user_id"]

    appliances = Appliance.query.filter_by(
        user_id=user_id
    ).order_by(Appliance.name).all()

    if not appliances:
        flash("Add your appliances before creating a solar plan.", "error")
        return redirect(url_for("appliances"))

    latest_plan = (
        Plan.query
        .filter_by(user_id=user_id)
        .order_by(Plan.created_at.desc(), Plan.id.desc())
        .first()
    )

    if request.method == "POST":
        errors, values = validate_plan(request.form)

        if not errors:
            town = api_client.get_town(values["place_id"])

            if town is None:
                flash(
                    "Weather service is not responding. Please try again.",
                    "error"
                )
                return render_template(
                    "planner.html",
                    appliances=appliances,
                    plan_data=request.form,
                    errors=errors,
                ), 503

            if not town:
                errors["place_id"] = "Choose a valid town."

        if errors:
            return render_template(
                "planner.html",
                appliances=appliances,
                plan_data=request.form,
                errors=errors,
            ), 400

        plan = Plan(
            user_id=user_id,
            place_id=values["place_id"],
            autonomy_days=values["autonomy_days"],
            has_grid=values["has_grid"],
            panel_w=values["panel_w"],
        )

        db.session.add(plan)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not save planner inputs")
            flash("Could not save your plan. Please try again.", "error")

            return render_template(
                "planner.html",
                appliances=appliances,
                plan_data=request.form,
                errors={}
            ), 500

        return redirect(url_for("planner_result"))

    plan_data = {
        "place_id": latest_plan.place_id if latest_plan else "",
        "autonomy_days": latest_plan.autonomy_days if latest_plan else 1,
        "has_grid": (
            "yes" if latest_plan and latest_plan.has_grid else "no"
        ),
        "panel_w": latest_plan.panel_w if latest_plan else 550,
    }

    return render_template(
        "planner.html",
        appliances=appliances,
        plan_data=plan_data,
        errors={},
    )


@app.route("/planner/result")
@login_required
def planner_result():
    user_id = session["user_id"]
    plan = (
        Plan.query
        .filter_by(user_id=user_id)
        .order_by(Plan.created_at.desc(), Plan.id.desc())
        .first()
    )

    if plan is None:
        flash("Create a plan first.", "error")
        return redirect(url_for("planner"))

    appliances = Appliance.query.filter_by(user_id=user_id).order_by(
        Appliance.name
    ).all()

    if not appliances:
        flash("Add your appliances before viewing a plan.", "error")
        return redirect(url_for("appliances"))

    town = api_client.get_town(plan.place_id)

    if town is None:
        return render_template(
            "planner_result.html",
            plan=plan,
            town=None,
            appliances=appliances,
            summary=None,
            result=None,
            error="Weather service is not responding. Please try again.",
        ), 503

    if not town:
        return render_template(
            "planner_result.html",
            plan=plan,
            town={},
            appliances=appliances,
            summary=None,
            result=None,
            error="This plan's town is invalid. Choose the town again.",
        ), 400

    appliance_data = [
        {
            "power_w": appliance.power_w,
            "quantity": appliance.quantity,
            "hours_day": appliance.hours_day,
            "hours_night": appliance.hours_night,
        }
        for appliance in appliances
    ]

    summary = sizing.load_summary(appliance_data)
    psh = api_client.get_winter_sun_hours(town["lat"], town["lon"])
    result = sizing.suggest_system(
        summary["e_day"],
        summary["e_night"],
        summary["peak_kw"],
        psh,
        plan.autonomy_days,
        plan.has_grid,
        plan.panel_w,
    )

    return render_template(
        "planner_result.html",
        plan=plan,
        town=town,
        appliances=appliances,
        summary=summary,
        result=result,
        error=None,
    )



@app.route("/planner/install", methods=["POST"])
@login_required
def planner_install():
    user_id = session["user_id"]

    plan = (
        Plan.query
        .filter_by(user_id=user_id)
        .order_by(Plan.created_at.desc(), Plan.id.desc())
        .first()
    )

    if plan is None:
        flash("Create a plan before installing it.", "error")
        return redirect(url_for("planner"))

    appliances = Appliance.query.filter_by(
        user_id=user_id
    ).all()

    if not appliances:
        flash("Add your appliances before installing a plan.", "error")
        return redirect(url_for("appliances"))

    town = api_client.get_town(plan.place_id)

    if town is None:
        flash("Weather service is not responding. Please try again.", "error")
        return redirect(url_for("planner_result"))

    if not town:
        flash("This plan's town is invalid. Choose the town again.", "error")
        return redirect(url_for("planner"))

    appliance_data = [
        {
            "power_w": appliance.power_w,
            "quantity": appliance.quantity,
            "hours_day": appliance.hours_day,
            "hours_night": appliance.hours_night,
        }
        for appliance in appliances
    ]

    summary = sizing.load_summary(appliance_data)

    psh = api_client.get_winter_sun_hours(
        town["lat"], town["lon"]
    )

    result = sizing.suggest_system(
        summary["e_day"],
        summary["e_night"],
        summary["peak_kw"],
        psh,
        plan.autonomy_days,
        plan.has_grid,
        plan.panel_w,
    )

    if result["inverter_kw"] is None:
        flash(
            "This system is over 12 kW. Please consult a certified installer.",
            "error"
        )
        return redirect(url_for("planner_result"))

    system = SolarSystem(
        user_id=user_id,
        place_id=plan.place_id,
        name="My planned system",
        panel_kw=result["installed_kwp"],
        battery_kwh=result["battery_kwh"],
        tilt=30,
        azimuth=0,
    )

    db.session.add(system)

    user = db.session.get(User, user_id)

    if user is None:
        db.session.rollback()
        flash("Your account could not be found.", "error")
        return redirect(url_for("login"))

    user.has_solar = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Could not install planned solar system")
        flash("Could not save your solar system. Please try again.", "error")
        return redirect(url_for("planner_result"))

    flash("Your solar system was added.", "success")
    return redirect(url_for("systems"))



if __name__ == "__main__":
    app.run(debug=True)
