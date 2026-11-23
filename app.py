"""
<YOUR PROJECT NAME> -- a Flask web app (team project starter).

Content comes from an external API (see api_client.py). The only data stored
is user accounts and their favorites (see models.py). Authentication is
email + password with Flask sessions.

Run locally:   flask run --debug    ->   http://127.0.0.1:5000
"""
import os
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort, g)  # g = per-request storage (Week 9: g.user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError  # raised when a unique rule (e.g. email) is broken

from models import db, User, Favorite, Appliance
import api_client
import solar  # our calculations (daily sunshine summary)
from validators import validate_signup, validate_login, validate_search

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


EXAMPLE_KW = 3          # example system size: 3 kW, a typical Lebanese home system
EXAMPLE_TILT = 30       # panels tilted 30°, close to the best angle for Lebanon's latitude
EXAMPLE_AZIMUTH = 0     # 0 = facing south in Open-Meteo (-90 east, 90 west)


def example_system(lat, lon):
    """Run a fixed 3 kW system through the solar functions for one town."""
    forecast = api_client.get_forecast(lat, lon, EXAMPLE_TILT, EXAMPLE_AZIMUTH)  # hourly tilted irradiance for 3 days
    if forecast is None:  # None = the API failed (our api_client contract)
        return None  # tell the route to show an error message
    hourly = solar.hourly_kwh(forecast, EXAMPLE_KW)  # kWh produced each hour
    daily = solar.daily_kwh(hourly)  # total kWh per day
    best = solar.best_day(daily)  # the day with the most production (or None)
    window = solar.best_window(hourly, best["date"]) if best else None  # best 4 hours of that day
    return {"kw": EXAMPLE_KW, "daily": daily, "best_day": best, "best_window": window}  # one dict for the template


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
    """Make the logged-in user (and their favorite ids) available in templates."""
    user = None
    favorite_ids = set()
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if user:
            favorite_ids = {f.item_id for f in user.favorites}
    return {"current_user": user, "favorite_ids": favorite_ids}


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
# A worked version of favorites below shows how session["user_id"] is used.

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
            flash("Great! You can add your system soon.")  # TODO feature/systems: redirect to url_for("system_new")
            return redirect(url_for("home"))  # temporary destination until the systems pages exist
        flash("Let's plan your system: start by adding your appliances.")  # first step of the planner
        return redirect(url_for("appliances"))  # Christ's appliance pages (the planner's input)
    return render_template("welcome.html")  # GET: show the question


# ---------- favorites (login required) -----------------------------
@app.route("/favorites")
@login_required
def favorites():
    items = Favorite.query.filter_by(user_id=session["user_id"]).all()
    return render_template("favorites.html", favorites=items)


@app.route("/favorites/add", methods=["POST"])
@login_required
def favorites_add():
    item_id = request.form.get("item_id", "").strip()
    if item_id:
        exists = Favorite.query.filter_by(
            user_id=session["user_id"], item_id=item_id).first()
        if exists:
            flash("Already in your favorites.")
        else:
            db.session.add(Favorite(
                user_id=session["user_id"], item_id=item_id,
                item_title=request.form.get("item_title", ""),
                item_image=request.form.get("item_image", "")))
            db.session.commit()
            flash("Saved to favorites.")
    return redirect(request.form.get("next") or url_for("favorites"))


@app.route("/favorites/remove", methods=["POST"])
@login_required
def favorites_remove():
    item_id = request.form.get("item_id", "").strip()
    fav = Favorite.query.filter_by(
        user_id=session["user_id"], item_id=item_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash("Removed from favorites.")
    return redirect(request.form.get("next") or url_for("favorites"))

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


if __name__ == "__main__":
    app.run(debug=True)
