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
GEOCODING_GET_URL = "https://geocoding-api.open-meteo.com/v1/get"  # one town by its id
MAX_PLACE_ID = 2_147_483_647  # largest Int32 number; Open-Meteo rejects bigger ids
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
    
    towns = []  # empty list that we fill with clean towns
    for place in data.get("results", []):  # loop over each raw town ([] if the key is missing)
        if place.get("id") is None:  # a town without an id can't be saved or opened
            continue  # skip it and go to the next town
        towns.append({  # add one clean town dict to our list
            "id": place.get("id"),  # Open-Meteo place id (the only value our DB stores)
            "name": place.get("name", ""),  # town name, e.g. "Jounieh"
            "region": place.get("admin1", ""),  # governorate, e.g. "Mount Lebanon"
            "district": place.get("admin2", ""),  # district, e.g. "Keserwan District" (can be missing)
            "lat": place.get("latitude"),  # latitude in degrees
            "lon": place.get("longitude"),  # longitude in degrees
        })  # end of the dict and of append(...)
    return towns  # [] if nothing matched, otherwise our clean towns


def get_town(place_id):  # get one town's details from its Open-Meteo id
    """Return one town dict; {} if the id is invalid, unknown or not in Lebanon; None if the API fails."""
    try:  # the id may come from a URL or a form, so it may not be a number
        place_id = int(place_id)  # accept 273140 or "273140"; "abc" or None raise an error
    except (TypeError, ValueError):  # TypeError for None, ValueError for "abc"
        return {}  # not a whole number -> no such town, no API call
    if not (1 <= place_id <= MAX_PLACE_ID):  # must be positive and fit in Int32
        return {}  # 0, negative or too big -> no such town, no API call
    try:  # code inside can fail because of the network or the API
        response = requests.get(GEOCODING_GET_URL, params={"id": place_id}, timeout=TIMEOUT)  # ask for one town, wait max 6 s
        if response.status_code in (400, 404):  # Open-Meteo answers "Location ID not found" with an error status
            return {}  # unknown id -> no such town (not an API failure)
        response.raise_for_status()  # any other HTTP error (500, ...) becomes an exception
        place = response.json()  # convert the JSON text into a Python dict (the town itself, no "results")
    except requests.RequestException as error:  # timeout, no internet, server error or invalid JSON
        logger.warning("Town lookup failed for id %s: %s", place_id, error)  # record the failure (no secrets)
        return None  # None = the API failed (decision B)
    if place.get("country_code") != "LB":  # only towns in Lebanon (someone could type another country's id in the URL)
        return {}  # outside Lebanon -> no such town for our app
    return {  # our clean town dict, same field names as search_towns
        "id": place.get("id"),  # Open-Meteo place id
        "name": place.get("name", ""),  # town name, e.g. "Jounieh"
        "region": place.get("admin1", ""),  # governorate, e.g. "Mount Lebanon"
        "district": place.get("admin2", ""),  # district, e.g. "Keserwan District" (can be missing)
        "lat": place.get("latitude"),  # latitude in degrees
        "lon": place.get("longitude"),  # longitude in degrees
    }  # end of the town dict


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
