"""Internal discovery service for  Escea AC."""
from pescea import Controller, Listener, discovery_service

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
)


class DiscoveryService(Listener):
    """Discovery data and interfacing with pescea library."""

    def __init__(self, hass):
        """Initialise discovery service."""
        super().__init__()
        self.hass = hass
        self.pi_disco = None

    # Listener interface
    def controller_discovered(self, ctrl: Controller) -> None:
        """Handle new controller discoverery."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    def controller_disconnected(self, ctrl: Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    def controller_reconnected(self, ctrl: Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    def controller_update(self, ctrl: Controller) -> None:
        """System update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)


async def async_start_discovery_service(hass: HomeAssistant):
    """Set up the pescea internal discovery."""
    disco = hass.data.get(DATA_DISCOVERY_SERVICE)
    if disco:
        # Already started
        return disco

    # discovery local services
    disco = DiscoveryService(hass)
    hass.data[DATA_DISCOVERY_SERVICE] = disco

    # Start the pescea discovery service, disco is the listener
    loop = hass.loop

    disco.pi_disco = discovery_service(disco, loop=loop)
    await disco.pi_disco.start_discovery()

    async def shutdown_event(event):
        await async_stop_discovery_service(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_event)

    return disco


async def async_stop_discovery_service(hass: HomeAssistant):
    """Stop the discovery service."""
    disco = hass.data.get(DATA_DISCOVERY_SERVICE)
    if not disco:
        return

    await disco.pi_disco.close()
    del hass.data[DATA_DISCOVERY_SERVICE]
