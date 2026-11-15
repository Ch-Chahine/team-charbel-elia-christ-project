"""
sizing.py -- System Planner maths for SolarSmart (Charbel).

Pure maths: no API calls and no database. The route passes the user's
appliances (as dicts) and the winter peak sun hours from api_client.
Every result is an ESTIMATE to confirm with a certified installer.
"""

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