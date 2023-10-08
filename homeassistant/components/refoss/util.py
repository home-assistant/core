"""Refoss helpers functions."""
from __future__ import annotations

from refoss_ha.discovery import Discovery

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import singleton


@singleton.singleton("refoss_discovery_server")
async def refoss_discovery_server(hass: HomeAssistant) -> Discovery:
    """Get refoss Discovery server."""
    discovery_server = Discovery()
    await discovery_server.initialize()

    @callback
    def shutdown_listener(ev: Event) -> None:
        """Shutdown Discovery server."""
        discovery_server.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)
    return discovery_server
