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


def best_window(hourly, date, hours=4):  # best block of consecutive hours on one day
    """Return {date, start, end, kwh} for the `hours` hours in a row with the most kWh on date; None if none."""
    day = [h for h in hourly if h["time"][:10] == date]  # keep only that day's hours (still in time order)
    if hours <= 0 or len(day) < hours:  # impossible window size, or not enough hours that day
        return None  # nothing to suggest
    best_start = 0  # position in `day` where the best block starts
    best_total = 0.0  # energy of the best block so far
    for i in range(len(day) - hours + 1):  # every possible block: 0..3, 1..4, 2..5, ...
        total = sum(h["kwh"] for h in day[i:i + hours])  # energy produced in this block
        if total > best_total:  # better than the best so far
            best_start, best_total = i, total  # remember where it starts and how much it makes
    if best_total <= 0:  # no sun at all that day (e.g. every value 0)
        return None  # no useful window
    first = day[best_start]["time"]  # e.g. "2026-11-22T11:00"
    last = day[best_start + hours - 1]["time"]  # e.g. "2026-11-22T14:00"
    start_hour = int(first[11:13]) - 1  # values are averages of the PREVIOUS hour, so "11:00" covers 10:00–11:00
    return {"date": date, "start": f"{start_hour:02d}:00", "end": last[11:16], "kwh": round(best_total, 2)}

def daily_kwh(hourly):  # add up the system's hourly kWh per day
    """Return [{date, kwh}] in date order from hourly_kwh's list."""
    days = {}  # "2026-11-22" -> total kWh so far that day
    for hour in hourly:  # each {"time": "2026-11-22T13:00", "kwh": 1.833}
        date = hour["time"][:10]  # first 10 characters = the date, "2026-11-22"
        days[date] = days.get(date, 0.0) + hour["kwh"]  # add this hour to its day's total (start at 0)
    return [{"date": date, "kwh": round(total, 2)} for date, total in days.items()]  # one dict per day, 2 decimals