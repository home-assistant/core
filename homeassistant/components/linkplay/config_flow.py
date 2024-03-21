"""Config flow to configure LinkPlay component."""

from linkplay.discovery import discover_linkplay_bridges

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    session = async_get_clientsession(hass)
    bridges = await discover_linkplay_bridges(session)
    return len(bridges) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "LinkPlay", _async_has_devices)
