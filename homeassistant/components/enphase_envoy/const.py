"""The enphase_envoy component."""


from homeassistant.const import ENERGY_WATT_HOUR, POWER_WATT

DOMAIN = "enphase_envoy"

PLATFORMS = ["sensor"]


COORDINATOR = "coordinator"
NAME = "name"

SENSORS = {
    "production": ("Current Energy Production", POWER_WATT),
    "daily_production": ("Today's Energy Production", ENERGY_WATT_HOUR),
    "seven_days_production": (
        "Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_production": ("Lifetime Energy Production", ENERGY_WATT_HOUR),
    "consumption": ("Current Energy Consumption", POWER_WATT),
    "daily_consumption": ("Today's Energy Consumption", ENERGY_WATT_HOUR),
    "seven_days_consumption": (
        "Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_consumption": ("Lifetime Energy Consumption", ENERGY_WATT_HOUR),
    "inverters": ("Inverter", POWER_WATT),
}
