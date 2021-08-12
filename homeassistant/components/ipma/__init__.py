"""Component for the Portuguese weather service - IPMA."""
from .config_flow import IpmaFlowHandler  # noqa: F401
from .const import DOMAIN  # noqa: F401

DEFAULT_NAME = "ipma"

PLATFORMS = ["weather"]


async def async_setup_entry(hass, entry):
    """Set up IPMA station as config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
