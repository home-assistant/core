"""Config flow for Haiku."""

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
from haiku.discover import *
from .const import DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    devices = await discover()
    if devices == [[],[]]:
        result = False
    else:
        result =  True
    return result


config_entry_flow.register_discovery_flow(
    DOMAIN, "Haiku", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
)
