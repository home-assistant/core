"""Refoss helpers functions."""

from refoss_ha.discovery import Discovery

from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton

from .const import DISCOVERY_SERVER


@singleton.singleton(DISCOVERY_SERVER)
async def refoss_discovery_server(hass: HomeAssistant) -> Discovery:
    """Get refoss Discovery server."""
    discovery_server = Discovery()
    await discovery_server.initialize()
    return discovery_server
