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