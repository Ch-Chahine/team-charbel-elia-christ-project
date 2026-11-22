"""
solar.py -- solar calculations for SolarSmart (Charbel).

Pure maths: no API calls and no database. The data comes from api_client.py.
"""

from sizing import PERFORMANCE_RATIO  # reuse the same 0.8 (one source of truth for both files)

def daily_sunshine(hours):  # turn the hourly forecast into one summary per day
    """Return a list of {date, kwh_m2, peak_time, peak_wm2}, one per day, in date order."""
    days = {}  # date -> that day's summary, e.g. "2026-11-15" -> {...}
    for hour in hours:  # each hour looks like {"time": "2026-11-15T12:00", "radiation": 585.0}
        date = hour["time"][:10]  # first 10 characters = the date, "2026-11-15"
        clock = hour["time"][11:16]  # characters 11 to 15 = the clock time, "12:00"
        radiation = hour["radiation"]  # sunshine in W/m², average over the previous hour
        if date not in days:  # first hour we see for this day -> start its summary
            days[date] = {"date": date, "kwh_m2": 0.0, "peak_time": clock, "peak_wm2": radiation}
        # Energy formula: an average power of X W/m² for 1 hour = X Wh/m²; divide by 1000 -> kWh/m²
        days[date]["kwh_m2"] += radiation / 1000  # add this hour's energy to the day's total
        if radiation > days[date]["peak_wm2"]:  # sunnier than the best hour so far today
            days[date]["peak_time"] = clock  # remember when
            days[date]["peak_wm2"] = radiation  # and how strong
    for day in days.values():  # after the loop, tidy every day
        day["kwh_m2"] = round(day["kwh_m2"], 2)  # 2 decimals is enough to display
    return list(days.values())  # dicts keep insertion order, so the days stay in date order


def hourly_kwh(forecast, panel_kw):  # energy the user's system makes each hour
    """Return [{time, kwh}] from get_forecast's hours ({time, irradiance, temperature}) for a panel_kw system."""
    if panel_kw <= 0:  # no panels -> no production (also avoids nonsense values)
        return []  # nothing to show
    hours = []  # one result per hour
    for hour in forecast:  # each hour looks like {"time": "2026-11-15T13:00", "irradiance": 763.8, ...}
        # Formula: kWh = panel_kw × (irradiance ÷ 1000) × PR
        # - at 1000 W/m² a panel gives its full rating, so irradiance ÷ 1000 is the fraction of full power
        # - PR = 0.8: heat, dust, wiring and inverter losses
        # - the value is an hourly average, so power for 1 hour = energy in kWh
        kwh = panel_kw * hour["irradiance"] / 1000 * PERFORMANCE_RATIO  # e.g. 3 × 0.7638 × 0.8 = 1.833 kWh
        hours.append({"time": hour["time"], "kwh": round(kwh, 3)})  # 3 decimals: small hours stay visible
    return hours  # same order as the forecast