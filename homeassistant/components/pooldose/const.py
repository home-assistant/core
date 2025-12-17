"""Constants for the Seko Pooldose integration."""

from __future__ import annotations

from homeassistant.const import UnitOfTemperature, UnitOfVolume, UnitOfVolumeFlowRate

DOMAIN = "pooldose"
MANUFACTURER = "SEKO"

# Unit mappings for select entities (water meter and flow rate)
# Keys match API values exactly: lowercase for m3/m3/h, uppercase L for L/L/s
UNIT_MAPPING: dict[str, str] = {
    # Temperature units
    "°C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    # Volume flow rate units
    "m3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "L/s": UnitOfVolumeFlowRate.LITERS_PER_SECOND,
    # Volume units
    "L": UnitOfVolume.LITERS,
    "m3": UnitOfVolume.CUBIC_METERS,
}
