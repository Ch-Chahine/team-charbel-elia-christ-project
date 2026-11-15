"""
sizing.py -- System Planner maths for SolarSmart (Charbel).

Pure maths: no API calls and no database. The route passes the user's
appliances (as dicts) and the winter peak sun hours from api_client.
Every result is an ESTIMATE to confirm with a certified installer.
"""
import math  # built-in: math.ceil rounds UP (you can't buy part of a panel)


PERFORMANCE_RATIO = 0.8  # real panels give ~80% of their rating (heat, wiring, inverter losses)
DEFAULT_PANEL_W = 550  # watts of one typical panel sold in Lebanon
PANEL_AREA_M2 = 2.6  # roof area of one 550 W panel, in m²
INVERTER_MARGIN = 1.25  # +25% so the inverter survives start-up surges (motors, compressors)
INVERTER_SIZES_KW = (3, 5, 8, 10, 12)  # standard inverter sizes we round up to
BATTERY_DOD = 0.8  # depth of discharge: LiFePO4 batteries can safely use 80% of their capacity
BATTERY_EFFICIENCY = 0.9  # 10% of the energy is lost charging and discharging
BATTERY_MODULE_KWH = 5  # batteries are sold in 5 kWh modules


def load_summary(appliances):  # how much energy the house needs
    """Return {e_day, e_night, peak_kw} from a list of {power_w, quantity, hours_day, hours_night}."""
    e_day = 0.0  # energy used during daylight (kWh/day)
    e_night = 0.0  # energy used at night (kWh/day)
    peak_w = 0.0  # power if everything is switched on at once (W)
    for item in appliances:  # one appliance at a time
        watts = item["power_w"] * item["quantity"]  # total power of this line, e.g. 2 fans x 60 W = 120 W
        # Formula: energy (Wh) = power (W) x hours; divide by 1000 -> kWh
        e_day += watts * item["hours_day"] / 1000  # E = Σ W x qty x hours_day / 1000
        e_night += watts * item["hours_night"] / 1000  # E_night = Σ W x qty x hours_night / 1000
        peak_w += watts  # peak = Σ W x qty (worst case: all on together)
    return {  # rounded for display
        "e_day": round(e_day, 2),  # kWh per day in daylight
        "e_night": round(e_night, 2),  # kWh per night
        "peak_kw": round(peak_w / 1000, 2),  # kW if everything runs at once
    }    


def panel_power(e_day, e_night, psh_winter):  # size of the panel array needed (kWp)
    """Return the panel power in kWp so the panels cover the day AND refill the battery for the night."""
    if psh_winter <= 0:  # no usable sun value -> avoid dividing by zero
        return 0.0  # nothing sensible to suggest
    # Formula: kWp = (E + E_night) ÷ (PSH_winter × PR)
    # - E + E_night: all energy used in 24 h comes from the panels (directly by day, via the battery at night)
    # - PSH_winter: peak sun hours of the darkest month, so the system is enough all year
    # - PR = 0.8: real panels give about 80% of their rating
    return round((e_day + e_night) / (psh_winter * PERFORMANCE_RATIO), 2)  # kWp, 2 decimals


def panels_needed(kwp, panel_w=DEFAULT_PANEL_W):  # turn kWp into whole panels
    """Return {panels, installed_kwp, roof_m2} for the needed kWp and one panel's watts."""
    if kwp <= 0 or panel_w <= 0:  # nothing needed, or an impossible panel size
        return {"panels": 0, "installed_kwp": 0.0, "roof_m2": 0.0}  # empty suggestion, no crash
    # Formula: panels = ceil(kWp × 1000 ÷ panel_W)  (kW -> W, then divide by one panel; always round UP)
    panels = math.ceil(kwp * 1000 / panel_w)  # e.g. 5830 W ÷ 550 W = 10.6 -> 11 panels
    installed_kwp = round(panels * panel_w / 1000, 2)  # the real power of those panels, e.g. 11 × 550 W = 6.05 kWp
    roof_m2 = round(panels * PANEL_AREA_M2, 1)  # roof space: about 2.6 m² per panel
    return {"panels": panels, "installed_kwp": installed_kwp, "roof_m2": roof_m2}  # what the page shows


def inverter_size(peak_kw):  # pick a standard inverter for the peak load
    """Return the smallest standard inverter (kW) that covers peak + 25%; 0 if no load; None if above 12 kW."""
    if peak_kw <= 0:  # no appliances -> nothing to power
        return 0  # no inverter needed
    # Formula: needed = peak × 1.25 (25% margin for start-up surges), then round UP to a standard size
    needed = peak_kw * INVERTER_MARGIN  # e.g. 3.5 kW × 1.25 = 4.375 kW
    for size in INVERTER_SIZES_KW:  # try 3, 5, 8, 10, 12 in order (smallest first)
        if size >= needed:  # the first size that is big enough
            return size  # e.g. 5 kW
    return None  # above 12 kW: too big for one standard inverter -> "ask an installer"