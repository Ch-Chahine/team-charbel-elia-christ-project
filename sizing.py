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
PANEL_W_PER_M2 = DEFAULT_PANEL_W / PANEL_AREA_M2  # power per m² of panel (~211.5 W/m²), so any panel size gets its area
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
    # Formula: panels = ceil(kWp × 1000 ÷ panel_W), always rounded UP.
    # round(kwp * 1000) first: decimals like 4.07 × 1000 give 4070.0000000000005 in a computer,
    # and ceil would wrongly turn 11.000000000000002 into 12 (bug found by Elia in review).
    panels = math.ceil(round(kwp * 1000) / panel_w)  # e.g. 5830 W ÷ 550 W = 10.6 -> 11 panels
    installed_kwp = round(panels * panel_w / 1000, 2)  # real power of those panels, e.g. 11 × 550 W = 6.05 kWp
    roof_m2 = round(panels * panel_w / PANEL_W_PER_M2, 1)  # roof space scales with panel size (550 W ≈ 2.6 m²)
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


def battery_size(e_night, autonomy_days):  # battery big enough for the night load
    """Return {battery_kwh, battery_modules}: 5 kWh modules covering the night load for the chosen days."""
    if e_night <= 0 or autonomy_days <= 0:  # nothing used at night, or the user wants no backup
        return {"battery_kwh": 0, "battery_modules": 0}  # no battery
    # Formula: battery = E_night × autonomy ÷ (DoD × efficiency), then round UP to whole 5 kWh modules
    # - DoD 0.8: we only use 80% of the battery so it lasts longer
    # - efficiency 0.9: 10% is lost charging and discharging
    needed = e_night * autonomy_days / (BATTERY_DOD * BATTERY_EFFICIENCY)  # e.g. 4 × 1 ÷ 0.72 = 5.56 kWh
    modules = math.ceil(needed / BATTERY_MODULE_KWH)  # 5.56 ÷ 5 = 1.11 -> 2 modules (always round UP)
    return {"battery_kwh": modules * BATTERY_MODULE_KWH, "battery_modules": modules}  # e.g. 10 kWh, 2 modules


def architecture(has_grid):  # which type of system fits the house
    """Return "hybrid" if the house has EDL or a generator, otherwise "off-grid"."""
    # Rule (proposal): EDL/generator present -> hybrid inverter (mixes solar, battery and the grid/generator);
    # none -> off-grid (solar + battery only). Pure on-grid is unsuitable in Lebanon because of power cuts.
    return "hybrid" if has_grid else "off-grid"  # one line: a conditional expression


def suggest_system(e_day, e_night, peak_kw, psh_winter, autonomy_days, has_grid, panel_w=DEFAULT_PANEL_W):
    """Return the full suggested system as one dict (see the contract shared with Christ)."""
    kwp = panel_power(e_day, e_night, psh_winter)  # step 1: panel power needed (kWp)
    panels = panels_needed(kwp, panel_w)  # step 2: whole panels, installed kWp, roof area
    battery = battery_size(e_night, autonomy_days)  # step 3: battery for the night (+ backup days)
    return {  # everything the result page shows, in one place
        "kwp": kwp,  # panel power needed, e.g. 5.83
        "panels": panels["panels"],  # number of panels, e.g. 11
        "panel_w": panel_w,  # watts of one panel, e.g. 550
        "installed_kwp": panels["installed_kwp"],  # real power of those panels, e.g. 6.05
        "roof_m2": panels["roof_m2"],  # roof space, e.g. 28.6
        "inverter_kw": inverter_size(peak_kw),  # step 4: standard inverter size, or None above 12 kW
        "battery_kwh": battery["battery_kwh"],  # e.g. 10
        "battery_modules": battery["battery_modules"],  # e.g. 2
        "architecture": architecture(has_grid),  # step 5: "hybrid" or "off-grid"
        "psh_winter": psh_winter,  # the winter sun value used, so the page can show it
    }