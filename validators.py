"""Server-side validation for sign-up, log-in, town search, solar systems, appliances and the planner."""
import math  # math.isfinite: refuse "nan" and "inf", which float() accepts
import re

EMAIL = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
from api_client import MIN_SEARCH_LENGTH, MAX_SEARCH_LENGTH, TOWN_NAME_PATTERN  # reuse the same search rules (one source of truth)


def validate_signup(form):
    errors = {}
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    confirm = form.get("confirm", "")
    if email == "":
        errors["email"] = "Email is required."
    elif len(email) > 255:  # the User.email column holds at most 255 characters
        errors["email"] = "Email must be at most 255 characters."  # PostgreSQL would reject it with an error
    elif not EMAIL.match(email):
        errors["email"] = "Enter a valid email address."
    if password == "":
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    elif len(password) > 128:  # hashing a huge password wastes server time (simple denial-of-service)
        errors["password"] = "Password must be at most 128 characters."  # 128 is plenty for any real password
    if confirm != password:  # was: confirm != "" and ... -> an EMPTY confirm box slipped through
        errors["confirm"] = "Passwords do not match."  # now the two boxes must always match
    return errors, email


def validate_login(form):
    errors = {}
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    if email == "":
        errors["email"] = "Email is required."
    if password == "":
        errors["password"] = "Password is required."
    return errors, email


def validate_search(args):  # check the town search box (?q=...) before calling the API
    errors = {}  # field name -> error message (same style as validate_signup)
    query = args.get("q", "").strip()  # text from the search box, without outer spaces
    if query == "":  # nothing typed
        errors["q"] = "Type a town name."  # message shown above the search box
    elif not (MIN_SEARCH_LENGTH <= len(query) <= MAX_SEARCH_LENGTH):  # outside 2..60
        errors["q"] = f"Town name must be {MIN_SEARCH_LENGTH}-{MAX_SEARCH_LENGTH} characters."  # length message
    elif not TOWN_NAME_PATTERN.match(query):  # forbidden characters
        errors["q"] = "Use letters, spaces, hyphens and apostrophes only."  # characters message
    return errors, query  # same shape as validate_signup: (errors, cleaned value)


# ---------- appliances and planner ---------------------------------

APPLIANCE_RANGES = {  # field -> (minimum, maximum, label, whole number?) -- same limits as the proposal
    "power_w": (1, 10000, "Power", True),  # watts of ONE unit
    "quantity": (1, 50, "Quantity", True),  # how many of them
    "hours_day": (0, 24, "Day hours", False),  # hours used in daylight (0.5 steps allowed)
    "hours_night": (0, 24, "Night hours", False),  # hours used at night
}


def validate_appliance(form):  # check the appliance form (add + edit); same (errors, values) shape as validate_system
    errors = {}  # field name -> error message shown under that field
    values = {}  # field name -> cleaned value, ready for the Appliance columns
    name = form.get("name", "").strip()  # appliance label without outer spaces
    if not 1 <= len(name) <= 40:  # empty or longer than the column (40)
        errors["name"] = "Name must be between 1 and 40 characters."
    values["name"] = name  # keep it so the form can show it again
    for field, (low, high, label, whole) in APPLIANCE_RANGES.items():  # check the 4 numbers the same way
        text = form.get(field, "").strip()  # what was typed, e.g. "150" or "2.5"
        try:  # int()/float() fail on "abc" or ""
            number = int(text) if whole else float(text)  # power and quantity must be whole numbers
        except ValueError:  # not a number at all
            errors[field] = f"{label} must be a {'whole ' if whole else ''}number."
            continue  # skip the range check for this field
        if not math.isfinite(number) or not low <= number <= high:  # outside the range, or nan / inf
            errors[field] = f"{label} must be between {low} and {high}."
        values[field] = number  # the cleaned number
    if ("hours_day" not in errors and "hours_night" not in errors  # both hour values are valid numbers...
            and values["hours_day"] + values["hours_night"] > 24):  # ...but a day only has 24 hours
        errors["hours_night"] = "Day and night hours together cannot be more than 24."
    return errors, values  # errors = {} when everything is valid


PLAN_CHOICES = {"autonomy_days": ("0", "1", "2", "3"), "has_grid": ("yes", "no")}  # the only values the selects can send


def validate_plan(form):  # check the planner form; returns (errors, values)
    """Validate and clean the planner inputs: town id, autonomy days, EDL/generator, panel watts."""
    errors = {}  # field name -> message
    values = {}  # field name -> cleaned value for the Plan columns
    place_text = form.get("place_id", "").strip()  # hidden field filled by the town search
    if place_text.isdecimal() and 1 <= int(place_text) <= 2147483647:  # whole number in Int32 range (Open-Meteo ids)
        values["place_id"] = int(place_text)  # the route still checks it exists with api_client.get_town
    else:  # empty, text, negative or too big
        errors["place_id"] = "Choose your town from the suggestions."
    autonomy = form.get("autonomy_days", "").strip()  # "0".."3" from the select
    if autonomy in PLAN_CHOICES["autonomy_days"]:  # allow-list: a tampered form can't send 99
        values["autonomy_days"] = int(autonomy)
    else:
        errors["autonomy_days"] = "Battery autonomy must be 0, 1, 2 or 3 days."
    grid = form.get("has_grid", "").strip().lower()  # "yes" or "no"
    if grid in PLAN_CHOICES["has_grid"]:
        values["has_grid"] = grid == "yes"  # True = hybrid, False = off-grid
    else:
        errors["has_grid"] = "Choose yes or no."
    panel_text = form.get("panel_w", "").strip()  # panel watts, e.g. "550"
    if panel_text.isdecimal() and 100 <= int(panel_text) <= 800:  # whole number in the proposal's range
        values["panel_w"] = int(panel_text)
    else:
        errors["panel_w"] = "Panel size must be a whole number from 100 to 800 W."
    return errors, values  # errors = {} when everything is valid

# The allowed range for each number on the solar system form (the same ranges as models.py).
SYSTEM_RANGES = {  # field name -> (minimum, maximum, label used in the error message)
    "panel_kw": (0.1, 50, "Panel power"),  # total panel power in kW
    "tilt": (0, 90, "Tilt"),  # 0 = flat, 90 = vertical
    "azimuth": (-180, 180, "Direction"),  # 0 = south, -90 = east, 90 = west
    "battery_kwh": (0, 100, "Battery"),  # 0 = no battery
}


def validate_system(form):  # check the solar system form (add + edit); same style as validate_signup
    errors = {}  # field name -> error message
    values = {}  # field name -> cleaned value, ready for the SolarSystem columns
    name = form.get("name", "").strip()  # the user's label, without outer spaces
    if not 1 <= len(name) <= 40:  # empty or too long (the column holds 40 characters)
        errors["name"] = "Name must be between 1 and 40 characters."
    values["name"] = name  # keep it, so the form can show it again
    for field, (low, high, label) in SYSTEM_RANGES.items():  # check the 4 numbers the same way
        text = form.get(field, "").strip()  # what was typed, e.g. "3.5"
        if field == "battery_kwh" and text == "":  # an empty battery box means "no battery"
            text = "0"  # treat it as 0 kWh
        try:  # float() fails on text like "abc" or ""
            number = float(text)  # "3.5" -> 3.5
        except ValueError:  # not a number at all
            errors[field] = f"{label} must be a number."
            continue  # skip the range check for this field
        if not low <= number <= high:  # outside the range; also catches "nan" and "inf"
            errors[field] = f"{label} must be between {low} and {high}."
        values[field] = number  # the cleaned number
    return errors, values  # errors = {} when everything is valid



# ----------  production log ---------------------------------------
MAX_LOG_KWH = 500  # proposal: 0-500 kWh per day
LOG_MAX_AGE_DAYS = 365  # readings older than a year are not useful for accuracy (keeps the table small)


def validate_log(form, today):  # check one production reading; today = Lebanese date, passed in by the route
    """Return (errors, values) with values = {date, actual_kwh}."""
    from datetime import date, timedelta  # only this function needs them
    errors = {}
    values = {}
    try:  # <input type="date"> sends "2026-11-26"; anything else raises ValueError
        day = date.fromisoformat(form.get("date", "").strip())
    except ValueError:
        errors["date"] = "Enter a valid date."
    else:
        if day > today:  # can't measure tomorrow's production
            errors["date"] = "The date cannot be in the future."
        elif day < today - timedelta(days=LOG_MAX_AGE_DAYS):  # too old
            errors["date"] = f"The date must be within the last {LOG_MAX_AGE_DAYS} days."
        values["date"] = day
    try:
        kwh = float(form.get("actual_kwh", "").strip())  # e.g. "12.4"
    except ValueError:
        errors["actual_kwh"] = "Production must be a number."
    else:
        if not math.isfinite(kwh) or not 0 <= kwh <= MAX_LOG_KWH:  # also refuses nan / inf
            errors["actual_kwh"] = f"Production must be between 0 and {MAX_LOG_KWH} kWh."
        values["actual_kwh"] = kwh
    return errors, values