"""The enphase_envoy component."""


from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import ENERGY_WATT_HOUR, POWER_WATT

DOMAIN = "enphase_envoy"

PLATFORMS = ["sensor"]


COORDINATOR = "coordinator"
NAME = "name"

SENSORS = {
    "production": ("Current Energy Production", POWER_WATT, STATE_CLASS_MEASUREMENT),
    "daily_production": ("Today's Energy Production", ENERGY_WATT_HOUR, None),
    "seven_days_production": (
        "Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
        None,
    ),
    "lifetime_production": ("Lifetime Energy Production", ENERGY_WATT_HOUR, None),
    "consumption": ("Current Energy Consumption", POWER_WATT, STATE_CLASS_MEASUREMENT),
    "daily_consumption": ("Today's Energy Consumption", ENERGY_WATT_HOUR, None),
    "seven_days_consumption": (
        "Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
        None,
    ),
    "lifetime_consumption": ("Lifetime Energy Consumption", ENERGY_WATT_HOUR, None),
    "inverters": ("Inverter", POWER_WATT, STATE_CLASS_MEASUREMENT),
}
