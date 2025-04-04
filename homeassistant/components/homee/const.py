"""Constants for the homee integration."""

from pyHomee.const import NodeProfile

from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

# General
DOMAIN = "homee"

# Sensor mappings
HOMEE_UNIT_TO_HA_UNIT = {
    "": None,
    "n/a": None,
    "text": None,
    "%": PERCENTAGE,
    "lx": LIGHT_LUX,
    "klx": LIGHT_LUX,
    "1/min": REVOLUTIONS_PER_MINUTE,
    "A": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "m/s": UnitOfSpeed.METERS_PER_SECOND,
    "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "°": DEGREE,
    "°F": UnitOfTemperature.FAHRENHEIT,
    "°C": UnitOfTemperature.CELSIUS,
    "K": UnitOfTemperature.KELVIN,
    "s": UnitOfTime.SECONDS,
    "min": UnitOfTime.MINUTES,
    "h": UnitOfTime.HOURS,
    "L": UnitOfVolume.LITERS,
}
OPEN_CLOSE_MAP = {
    0.0: "open",
    1.0: "closed",
    2.0: "partial",
    3.0: "opening",
    4.0: "closing",
}
OPEN_CLOSE_MAP_REVERSED = {
    0.0: "closed",
    1.0: "open",
    2.0: "partial",
    3.0: "closing",
    4.0: "opening",
}
WINDOW_MAP = {
    0.0: "closed",
    1.0: "open",
    2.0: "tilted",
}
WINDOW_MAP_REVERSED = {0.0: "open", 1.0: "closed", 2.0: "tilted"}

# Profile Groups
CLIMATE_PROFILES = [
    NodeProfile.COSI_THERM_CHANNEL,
    NodeProfile.HEATING_SYSTEM,
    NodeProfile.RADIATOR_THERMOSTAT,
    NodeProfile.ROOM_THERMOSTAT,
    NodeProfile.ROOM_THERMOSTAT_WITH_HUMIDITY_SENSOR,
    NodeProfile.THERMOSTAT_WITH_HEATING_AND_COOLING,
    NodeProfile.WIFI_RADIATOR_THERMOSTAT,
    NodeProfile.WIFI_ROOM_THERMOSTAT,
]

LIGHT_PROFILES = [
    NodeProfile.DIMMABLE_COLOR_LIGHT,
    NodeProfile.DIMMABLE_COLOR_METERING_PLUG,
    NodeProfile.DIMMABLE_COLOR_TEMPERATURE_LIGHT,
    NodeProfile.DIMMABLE_EXTENDED_COLOR_LIGHT,
    NodeProfile.DIMMABLE_LIGHT,
    NodeProfile.DIMMABLE_LIGHT_WITH_BRIGHTNESS_SENSOR,
    NodeProfile.DIMMABLE_LIGHT_WITH_BRIGHTNESS_AND_PRESENCE_SENSOR,
    NodeProfile.DIMMABLE_LIGHT_WITH_PRESENCE_SENSOR,
    NodeProfile.DIMMABLE_METERING_SWITCH,
    NodeProfile.DIMMABLE_METERING_PLUG,
    NodeProfile.DIMMABLE_PLUG,
    NodeProfile.DIMMABLE_RGBWLIGHT,
    NodeProfile.DIMMABLE_SWITCH,
    NodeProfile.WIFI_DIMMABLE_RGBWLIGHT,
    NodeProfile.WIFI_DIMMABLE_LIGHT,
    NodeProfile.WIFI_ON_OFF_DIMMABLE_METERING_SWITCH,
]

# Climate Presets
PRESET_MANUAL = "manual"
