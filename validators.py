"""Server-side validation for sign-up, log-in, town search and solar systems."""
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
