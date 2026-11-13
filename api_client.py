"""
api_client.py  --  ALL calls to your external API live here (one place).

RIGHT NOW this returns a few SAMPLE items so the app runs out of the box.
TODO (your team): replace the sample data with real calls to your chosen free
API, keeping the SAME return shapes so the rest of the app keeps working:

    search(query)   -> a list of dicts, each: {"id", "title", "image"}
    get_item(id)    -> one dict: {"id", "title", "image", "description"}
"""
import logging
import re

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 6  # seconds; give up instead of hanging if the API is slow

GEOCODING_SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"  # base URL of the town search; query goes in params
MIN_SEARCH_LENGTH = 2  # shortest search allowed; Open-Meteo returns nothing for 1 character
MAX_SEARCH_LENGTH = 60  # longest search allowed; blocks huge inputs
TOWN_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ\u0600-\u06FF .'-]+$")  # whole text: letters, space . ' - only

def search_towns(name):  # find towns in Lebanon whose name matches what the user typed
    """Return a list of towns; [] if input is invalid or nothing matches; None if the API fails."""
    if not isinstance(name, str):  # reject anything that is not text (e.g. None, a number)
        return []  # invalid input -> no API call
    name = name.strip()  # remove spaces at both ends: "  Jounieh " -> "Jounieh"
    if not (MIN_SEARCH_LENGTH <= len(name) <= MAX_SEARCH_LENGTH):  # length must be 2..60
        return []  # too short or too long -> no API call
    if not TOWN_NAME_PATTERN.match(name):  # only letters, space . ' - are allowed
        return []  # forbidden characters -> no API call
    params = {  # query parameters; requests URL-encodes them safely
        "name": name,  # the cleaned text the user typed
        "countryCode": "LB",  # only towns in Lebanon
        "count": 10,  # at most 10 towns in the answer
        "language": "en",  # town and region names in English
        "format": "json",  # ask for a JSON reply
    }
    try:  # code inside can fail because of the network or the API
        response = requests.get(GEOCODING_SEARCH_URL, params=params, timeout=TIMEOUT)  # send request, wait max 6 s
        response.raise_for_status()  # turn HTTP errors (400, 500, ...) into an exception
        data = response.json()  # convert the JSON text into a Python dict
    except requests.RequestException as error:  # timeout, no internet, HTTP error or invalid JSON
        logger.warning("Town search failed for %r: %s", name, error)  # record the failure (no secrets)
        return None  # None = the API failed (decision A)
    return data.get("results", [])  # TEMPORARY: raw results; we reshape them in the next step

# ----- temporary sample data (delete once your API works) -----
_SAMPLE = [
    {"id": "1", "title": "Example Item One",
     "image": "https://picsum.photos/id/1011/400/300",
     "description": "Replace this with a real description from your API."},
    {"id": "2", "title": "Example Item Two",
     "image": "https://picsum.photos/id/1025/400/300",
     "description": "Replace this with a real description from your API."},
    {"id": "3", "title": "Example Item Three",
     "image": "https://picsum.photos/id/1039/400/300",
     "description": "Replace this with a real description from your API."},
]


def search(query):
    """Return a list of items matching the query."""
    # TODO: call your API instead, e.g.
    #   r = requests.get("https://api.example.com/search",
    #                    params={"q": query}, timeout=TIMEOUT)
    #   if r.status_code != 200:
    #       return []
    #   data = r.json()
    #   return [{"id": x["id"], "title": x["name"], "image": x["thumb"]}
    #           for x in data["results"]]
    q = query.lower()
    hits = [it for it in _SAMPLE if q in it["title"].lower()]
    return hits or _SAMPLE


def get_item(item_id):
    """Return one item by its id, or None if not found."""
    # TODO: call your API for one item, e.g.
    #   r = requests.get(f"https://api.example.com/item/{item_id}", timeout=TIMEOUT)
    #   ...
    for it in _SAMPLE:
        if it["id"] == item_id:
            return it
    return None
