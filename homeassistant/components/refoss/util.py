"""Refoss helpers functions."""
from __future__ import annotations

from refoss_ha.socket_server import SocketServerProtocol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import singleton


@singleton.singleton("refoss_socket_server")
async def get_refoss_socket_server(hass: HomeAssistant) -> SocketServerProtocol:
    """Get refoss socket server."""
    socket_server = SocketServerProtocol()
    await socket_server.initialize()

    @callback
    def shutdown_listener(ev: Event) -> None:
        """Shutdown socket_server."""
        socket_server.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)
    return socket_server
