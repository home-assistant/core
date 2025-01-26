"""Constants for the homee integration."""

from homeassistant.const import (
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
    3.0: "cosing",
    4.0: "opening",
}
WINDOW_MAP = {
    0.0: "closed",
    1.0: "open",
    2.0: "tilted",
}
WINDOW_MAP_REVERSED = {0.0: "open", 1.0: "closed", 2.0: "tilted"}
