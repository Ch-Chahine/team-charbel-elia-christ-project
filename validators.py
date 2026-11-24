"""Server-side validation for sign-up, log-in and town search."""
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
    elif not EMAIL.match(email):
        errors["email"] = "Enter a valid email address."
    if password == "":
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    if confirm != "" and confirm != password:
        errors["confirm"] = "Passwords do not match."
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


def validate_plan(form):
    """Validate and clean planner inputs."""

    errors = {}

    # Town ID
    place_id_raw = form.get("place_id", "").strip()

    if not place_id_raw.isdecimal():
        errors["place_id"] = "Choose a valid town."
        place_id = None
    else:
        place_id = int(place_id_raw)

        if place_id <= 0 or place_id > 2147483647:
            errors["place_id"] = "Choose a valid town."
            place_id = None

    # Battery autonomy
    autonomy_raw = form.get("autonomy_days", "").strip()

    if not autonomy_raw.isdecimal():
        errors["autonomy_days"] = (
            "Battery autonomy must be a whole number from 0 to 3."
        )
        autonomy_days = None
    else:
        autonomy_days = int(autonomy_raw)

        if not 0 <= autonomy_days <= 3:
            errors["autonomy_days"] = (
                "Battery autonomy must be from 0 to 3."
            )

    # EDL / generator availability
    has_grid_raw = form.get("has_grid", "").strip().lower()

    if has_grid_raw not in {"yes", "no"}:
        errors["has_grid"] = "Choose yes or no."
        has_grid = None
    else:
        has_grid = has_grid_raw == "yes"

    # Panel wattage
    panel_raw = form.get("panel_w", "").strip()

    if not panel_raw.isdecimal():
        errors["panel_w"] = (
            "Panel size must be a whole number from 100 to 800 W."
        )
        panel_w = None
    else:
        panel_w = int(panel_raw)

        if not 100 <= panel_w <= 800:
            errors["panel_w"] = (
                "Panel size must be from 100 to 800 W."
            )

    values = {
        "place_id": place_id,
        "autonomy_days": autonomy_days,
        "has_grid": has_grid,
        "panel_w": panel_w,
    }

    return errors, values
