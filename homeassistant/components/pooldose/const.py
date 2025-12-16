"""Constants for the Seko Pooldose integration."""

from __future__ import annotations

from homeassistant.const import UnitOfTemperature, UnitOfVolume, UnitOfVolumeFlowRate

DOMAIN = "pooldose"
MANUFACTURER = "SEKO"

# Forward Mapping: Device/API units (upper case) to Home Assistant units
UNIT_MAPPING: dict[str, str] = {
    # Temperature units
    "°C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    # Volume flow rate units
    "M3/H": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "L/S": UnitOfVolumeFlowRate.LITERS_PER_SECOND,
    # Volume units
    "L": UnitOfVolume.LITERS,
    "M3": UnitOfVolume.CUBIC_METERS,
}

# Reverse mapping: Home Assistant units to device/API units
REVERSE_UNIT_MAPPING: dict[str, str] = {
    # Volume flow rate units
    UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: "m3/h",
    UnitOfVolumeFlowRate.LITERS_PER_SECOND: "L/s",
    # Volume units
    UnitOfVolume.LITERS: "L",
    UnitOfVolume.CUBIC_METERS: "m3",
}
