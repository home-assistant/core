"""Constants for the duotecno integration."""
from homeassistant.components.climate import HVACMode

DOMAIN = "duotecno"

HVACMODE = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
}
