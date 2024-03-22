"""Config flow to configure LinkPlay component."""

from linkplay.controller import LinkPlayController

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    session = async_get_clientsession(hass)
    controller = LinkPlayController(session)
    await controller.discover_bridges()
    return len(controller.bridges) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "LinkPlay", _async_has_devices)
