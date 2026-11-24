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
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Favorite, Appliance, Plan, SolarSystem
import api_client
import solar  # our calculations (daily sunshine summary)
import sizing
from validators import validate_signup, validate_login, validate_search, validate_plan

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


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
    return render_template("town.html", town=data, api_failed=False,  # show the town
                           forecast=forecast, forecast_failed=hours is None)  # + forecast, or a "forecast unavailable" flag


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

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # TODO: implement sign-up (see the Sessions & Login slides).
        pass
    return render_template("signup.html", errors={}, data={})



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # TODO: implement log-in (see the Sessions & Login slides).
        pass
    return render_template("login.html", errors={}, data={})



@app.route("/logout")
def logout():
    # TODO: end the session (hint: session.clear()), then redirect home.
    return redirect(url_for("home"))


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
