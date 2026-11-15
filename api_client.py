"""
api_client.py -- all calls to the Open-Meteo API live here (one place).

Geocoding (towns in Lebanon):
    search_towns(name)  -> list of {id, name, region, district, lat, lon};
                           [] if input is invalid or nothing matches; None if the API fails
    get_town(place_id)  -> one {id, name, region, district, lat, lon};
                           {} if the id is invalid, unknown or not in Lebanon; None if the API fails

Forecast (next 3 days, Beirut time):
    get_town_forecast(lat, lon)  -> list of {time, radiation} on a flat surface (W/m²)
    get_forecast(lat, lon, tilt, azimuth, past_days=0)
                                 -> list of {time, irradiance, temperature} on tilted panels
    Both: [] if inputs are invalid; None if the API fails.

Planner:
    get_winter_sun_hours(lat, lon) -> darkest month's average peak sun hours of last year
                                      (MJ/m² ÷ 3.6); DEFAULT_WINTER_SUN_HOURS if anything fails

Every call validates its input first, uses a timeout, catches network errors,
and logs failures (never secrets). Successful answers are cached in memory
(towns and winter sun hours 24 h, forecasts 30 min); failures are never cached.
Our database stores only place_id; names, coordinates and forecasts are always
fetched from the API.
"""

import logging  # built-in: write warning messages when the API fails
import re  # built-in: regular expressions, to check allowed characters
import time  # built-in: current time in seconds, to know when a cache entry expires
from datetime import date  # built-in: today's date, to know which year was "last year"

import requests  # installed package: makes the HTTP calls to Open-Meteo

logger = logging.getLogger(__name__)  # logger named "api_client"; shows in terminal + Render logs

TIMEOUT = 6  # seconds; give up instead of hanging if the API is slow

GEOCODING_SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"  # base URL of the town search; query goes in params
GEOCODING_GET_URL = "https://geocoding-api.open-meteo.com/v1/get"  # one town by its id
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"  # weather forecast API (hourly sunshine)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"  # past weather: one full year of daily sunshine
DEFAULT_WINTER_SUN_HOURS = 2.5  # fallback peak sun hours if the archive fails (Jounieh's real Dec 2025 = 2.46)
MAX_PLACE_ID = 2_147_483_647  # largest Int32 number; Open-Meteo rejects bigger ids
MIN_SEARCH_LENGTH = 2  # shortest search allowed; Open-Meteo returns nothing for 1 character
MAX_SEARCH_LENGTH = 60  # longest search allowed; blocks huge inputs
TOWN_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ؀-ۿ .'-]+$")  # whole text: letters, space . ' - only
CACHE_MAX_ITEMS = 500  # safety limit so the cache can't grow forever (search keys come from users)
TOWN_CACHE_SECONDS = 24 * 60 * 60  # towns and winter sun hours: 24 hours (they almost never change)
FORECAST_CACHE_SECONDS = 30 * 60  # forecasts: 30 minutes (Open-Meteo updates them during the day)
_cache = {}  # key -> (expires_at, value); kept in memory, one cache per server process


def _cache_get(key):  # look up a remembered answer
    """Return the cached value for key, or None if it is missing or expired."""
    entry = _cache.get(key)  # (expires_at, value) or None if never stored
    if entry is None:  # nothing remembered for this key
        return None  # caller must call the API
    expires_at, value = entry  # unpack the pair
    if time.time() > expires_at:  # too old
        del _cache[key]  # forget it
        return None  # caller must call the API again
    return value  # still fresh -> use it, no API call


def _cache_set(key, value, seconds):  # remember an answer for a while
    """Store value under key for the given number of seconds."""
    if len(_cache) >= CACHE_MAX_ITEMS:  # cache is full
        _cache.clear()  # simplest safe option: start empty again
    _cache[key] = (time.time() + seconds, value)  # remember the value and when it expires


def search_towns(name):  # find towns in Lebanon whose name matches what the user typed
    """Return a list of towns; [] if input is invalid or nothing matches; None if the API fails."""
    if not isinstance(name, str):  # reject anything that is not text (e.g. None, a number)
        return []  # invalid input -> no API call
    name = name.strip()  # remove spaces at both ends: "  Jounieh " -> "Jounieh"
    if not (MIN_SEARCH_LENGTH <= len(name) <= MAX_SEARCH_LENGTH):  # length must be 2..60
        return []  # too short or too long -> no API call
    if not TOWN_NAME_PATTERN.match(name):  # only letters, space . ' - are allowed
        return []  # forbidden characters -> no API call
    cache_key = ("search", name.lower())  # label for this question; lower() so "Jounieh" and "jounieh" share it
    cached = _cache_get(cache_key)  # already asked recently?
    if cached is not None:  # yes, and still fresh ([] counts too: "no towns" is a valid answer)
        return cached  # answer from memory, no API call
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
        return None  # None = the API failed (decision A), never cached

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
    _cache_set(cache_key, towns, TOWN_CACHE_SECONDS)  # remember the result for 24 h (after the loop, once)
    return towns  # [] if nothing matched, otherwise our clean towns


def get_town(place_id):  # get one town's details from its Open-Meteo id
    """Return one town dict; {} if the id is invalid, unknown or not in Lebanon; None if the API fails."""
    try:  # the id may come from a URL or a form, so it may not be a number
        place_id = int(place_id)  # accept 273140 or "273140"; "abc" or None raise an error
    except (TypeError, ValueError):  # TypeError for None, ValueError for "abc"
        return {}  # not a whole number -> no such town, no API call
    if not (1 <= place_id <= MAX_PLACE_ID):  # must be positive and fit in Int32
        return {}  # 0, negative or too big -> no such town, no API call
    cache_key = ("town", place_id)  # label for this question, e.g. ("town", 273140)
    cached = _cache_get(cache_key)  # already looked up recently?
    if cached is not None:  # yes, and still fresh
        return cached  # answer from memory, no API call
    try:  # code inside can fail because of the network or the API
        response = requests.get(GEOCODING_GET_URL, params={"id": place_id}, timeout=TIMEOUT)  # ask for one town, wait max 6 s
        if response.status_code in (400, 404):  # Open-Meteo answers "Location ID not found" with an error status
            return {}  # unknown id -> no such town (not an API failure)
        response.raise_for_status()  # any other HTTP error (500, ...) becomes an exception
        place = response.json()  # convert the JSON text into a Python dict (the town itself, no "results")
    except requests.RequestException as error:  # timeout, no internet, server error or invalid JSON
        logger.warning("Town lookup failed for id %s: %s", place_id, error)  # record the failure (no secrets)
        return None  # None = the API failed (decision B), never cached
    if place.get("country_code") != "LB":  # only towns in Lebanon (someone could type another country's id in the URL)
        return {}  # outside Lebanon -> no such town for our app
    town = {  # our clean town dict, same field names as search_towns
        "id": place.get("id"),  # Open-Meteo place id
        "name": place.get("name", ""),  # town name, e.g. "Jounieh"
        "region": place.get("admin1", ""),  # governorate, e.g. "Mount Lebanon"
        "district": place.get("admin2", ""),  # district, e.g. "Keserwan District" (can be missing)
        "lat": place.get("latitude"),  # latitude in degrees
        "lon": place.get("longitude"),  # longitude in degrees
    }  # end of the town dict
    _cache_set(cache_key, town, TOWN_CACHE_SECONDS)  # remember this town for 24 h
    return town  # the clean town


def get_town_forecast(lat, lon):  # hourly sunshine on a flat surface for the next 3 days
    """Return a list of {time, radiation}; [] if lat/lon are invalid; None if the API fails."""
    try:  # lat/lon may come from anywhere, so they may not be numbers
        lat = float(lat)  # accept 33.98 or "33.98"; None or "abc" raise an error
        lon = float(lon)  # same for longitude
    except (TypeError, ValueError):  # TypeError for None, ValueError for "abc"
        return []  # not numbers -> invalid, no API call
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):  # valid ranges on Earth (Open-Meteo rejects others)
        return []  # out of range -> invalid, no API call
    cache_key = ("town_forecast", round(lat, 4), round(lon, 4))  # label for this question (4 decimals ≈ 11 m)
    cached = _cache_get(cache_key)  # already fetched in the last 30 minutes?
    if cached is not None:  # yes, and still fresh
        return cached  # answer from memory, no API call
    params = {  # query parameters; requests URL-encodes them safely
        "latitude": lat,  # the town's latitude
        "longitude": lon,  # the town's longitude
        "hourly": "shortwave_radiation",  # sunshine on a flat surface, W/m², average of the previous hour
        "timezone": "Asia/Beirut",  # times in Lebanese time, not UTC
        "forecast_days": 3,  # today + the next 2 days (72 hours)
    }
    try:  # code inside can fail because of the network or the API
        response = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)  # send request, wait max 6 s
        response.raise_for_status()  # turn HTTP errors (400, 500, ...) into an exception
        data = response.json()  # convert the JSON text into a Python dict
    except requests.RequestException as error:  # timeout, no internet, HTTP error or invalid JSON
        logger.warning("Forecast failed for %s,%s: %s", lat, lon, error)  # record the failure (no secrets)
        return None  # None = the API failed, never cached
    hourly = data.get("hourly", {})  # the hourly block ({} if missing, so no KeyError)
    times = hourly.get("time", [])  # list of times, e.g. "2026-11-15T12:00"
    values = hourly.get("shortwave_radiation", [])  # list of W/m², same order as times
    hours = []  # our clean list, one dict per hour
    for when, radiation in zip(times, values):  # pair item 0 with item 0, item 1 with item 1, ...
        if radiation is None:  # the API had no value for this hour
            continue  # skip it rather than invent a number
        hours.append({"time": when, "radiation": radiation})  # one clean hour
    _cache_set(cache_key, hours, FORECAST_CACHE_SECONDS)  # remember the forecast for 30 minutes
    return hours  # 72 hours normally; [] if the API sent no data


def get_forecast(lat, lon, tilt, azimuth, past_days=0):  # hourly sunshine on the user's tilted panels
    """Return a list of {time, irradiance, temperature}; [] if inputs are invalid; None if the API fails."""
    try:  # all inputs may come from forms or the database, so convert them first
        lat = float(lat)  # latitude in degrees
        lon = float(lon)  # longitude in degrees
        tilt = float(tilt)  # panel angle: 0 = flat, 90 = vertical
        azimuth = float(azimuth)  # panel direction: 0 = south, -90 = east, 90 = west
        past_days = int(past_days)  # extra past days (used to compare with logged production)
    except (TypeError, ValueError):  # None or text that isn't a number
        return []  # invalid -> no API call
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):  # valid ranges on Earth
        return []  # invalid coordinates -> no API call
    if not (0 <= tilt <= 90 and -180 <= azimuth <= 180 and 0 <= past_days <= 7):  # same ranges as Elia's validators
        return []  # invalid panel settings -> no API call
    cache_key = ("forecast", round(lat, 4), round(lon, 4), tilt, azimuth, past_days)  # every input changes the answer
    cached = _cache_get(cache_key)  # already fetched in the last 30 minutes?
    if cached is not None:  # yes, and still fresh
        return cached  # answer from memory, no API call
    params = {  # query parameters; requests URL-encodes them safely
        "latitude": lat,  # the system's town latitude
        "longitude": lon,  # the system's town longitude
        "hourly": "global_tilted_irradiance,temperature_2m",  # sunshine on the tilted panel + air temperature
        "tilt": tilt,  # panel angle
        "azimuth": azimuth,  # panel direction (Open-Meteo uses the same convention as our database)
        "timezone": "Asia/Beirut",  # times in Lebanese time
        "forecast_days": 3,  # today + the next 2 days
        "past_days": past_days,  # 0 normally; 7 to compare with the production log
    }
    try:  # code inside can fail because of the network or the API
        response = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)  # send request, wait max 6 s
        response.raise_for_status()  # turn HTTP errors (400, 500, ...) into an exception
        data = response.json()  # convert the JSON text into a Python dict
    except requests.RequestException as error:  # timeout, no internet, HTTP error or invalid JSON
        logger.warning("System forecast failed for %s,%s: %s", lat, lon, error)  # record the failure (no secrets)
        return None  # None = the API failed, never cached
    hourly = data.get("hourly", {})  # the hourly block ({} if missing)
    times = hourly.get("time", [])  # list of times
    irradiance = hourly.get("global_tilted_irradiance", [])  # W/m² on the panel, same order as times
    temperature = hourly.get("temperature_2m", [])  # °C, same order as times
    hours = []  # our clean list, one dict per hour
    for when, sun, temp in zip(times, irradiance, temperature):  # walk the three lists together
        if sun is None:  # the API had no sunshine value for this hour
            continue  # skip it rather than invent a number
        hours.append({"time": when, "irradiance": sun, "temperature": temp})  # one clean hour
    _cache_set(cache_key, hours, FORECAST_CACHE_SECONDS)  # remember the forecast for 30 minutes
    return hours  # 72 hours (+ 24 per past day); [] if no data


def get_winter_sun_hours(lat, lon):  # peak sun hours of the darkest month, for the planner
    """Return the lowest monthly average of daily peak sun hours last year; DEFAULT_WINTER_SUN_HOURS if anything fails."""
    try:  # lat/lon may come from anywhere, so convert them first
        lat = float(lat)  # latitude in degrees
        lon = float(lon)  # longitude in degrees
    except (TypeError, ValueError):  # None or text that isn't a number
        return DEFAULT_WINTER_SUN_HOURS  # the planner always needs a number
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):  # valid ranges on Earth
        return DEFAULT_WINTER_SUN_HOURS  # invalid coordinates -> safe fallback, no API call
    last_year = date.today().year - 1  # e.g. 2025 when today is 2026 (a complete year, with every month)
    cache_key = ("winter_sun", round(lat, 4), round(lon, 4), last_year)  # last year is part of the question
    cached = _cache_get(cache_key)  # already computed in the last 24 hours?
    if cached is not None:  # yes, and still fresh
        return cached  # answer from memory, no API call
    params = {  # query parameters; requests URL-encodes them safely
        "latitude": lat,  # the town's latitude
        "longitude": lon,  # the town's longitude
        "start_date": f"{last_year}-01-01",  # 1 January of last year
        "end_date": f"{last_year}-12-31",  # 31 December of last year
        "daily": "shortwave_radiation_sum",  # total sunshine per day, in MJ/m²
        "timezone": "Asia/Beirut",  # days counted in Lebanese time
    }
    try:  # code inside can fail because of the network or the API
        response = requests.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)  # send request, wait max 6 s
        response.raise_for_status()  # turn HTTP errors (400, 500, ...) into an exception
        data = response.json()  # convert the JSON text into a Python dict
    except requests.RequestException as error:  # timeout, no internet, HTTP error or invalid JSON
        logger.warning("Winter sun hours failed for %s,%s: %s (using %s)", lat, lon, error, DEFAULT_WINTER_SUN_HOURS)
        return DEFAULT_WINTER_SUN_HOURS  # fallback so the planner still works (not cached)
    daily = data.get("daily", {})  # the daily block ({} if missing)
    months = {}  # "2025-01" -> list of that month's daily peak sun hours
    for day, mj in zip(daily.get("time", []), daily.get("shortwave_radiation_sum", [])):  # walk days and values together
        if mj is None:  # no value for this day
            continue  # skip it rather than invent a number
        month = day[:7]  # "2025-01-15"[:7] -> "2025-01"
        if month not in months:  # first day we see for this month
            months[month] = []  # start its list
        # Conversion: 1 kWh = 3.6 MJ, so MJ/m² ÷ 3.6 = kWh/m² = peak sun hours for that day
        months[month].append(mj / 3.6)  # add this day's peak sun hours
    if not months:  # the API answered but sent no usable data
        logger.warning("Winter sun hours: no data for %s,%s (using %s)", lat, lon, DEFAULT_WINTER_SUN_HOURS)
        return DEFAULT_WINTER_SUN_HOURS  # fallback (not cached)
    averages = [sum(values) / len(values) for values in months.values()]  # one average per month
    winter = round(min(averages), 2)  # the darkest month's average, e.g. 2.46
    _cache_set(cache_key, winter, TOWN_CACHE_SECONDS)  # remember it for 24 h (real values only, never the fallback)
    return winter  # peak sun hours for sizing