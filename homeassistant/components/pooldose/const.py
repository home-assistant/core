"""Constants for the Seko Pooldose integration."""

from __future__ import annotations

from homeassistant.const import UnitOfTemperature, UnitOfVolumeFlowRate

DOMAIN = "pooldose"
MANUFACTURER = "SEKO"

# Mapping of device units to Home Assistant units
UNIT_MAPPING: dict[str, str] = {
    # Temperature units
    "°C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    # Volume flow rate units
    "m3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "L/s": UnitOfVolumeFlowRate.LITERS_PER_SECOND,
}
