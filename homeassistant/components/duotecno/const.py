"""Constants for the duotecno integration."""
from typing import Final

from homeassistant.components.climate import HVACMode

DOMAIN: Final = "duotecno"

HVACMODE: Final = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
}

PRESETMODES: Final = {
    "Sun": 0,
    "Half Sun": 1,
    "Moon": 2,
    "Half Moon": 3,
}
