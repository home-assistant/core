"""Support for showing device locations."""
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "map"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the built-in map panel."""
    frontend.async_register_built_in_panel(hass, "map", "map", "hass:tooltip-account")
    return True
