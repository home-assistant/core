"""Internal discovery service for  iZone AC."""

import logging
from asyncio import Event
from typing import Dict

import pizone

from homeassistant.const import CONF_EXCLUDE, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)

from .climate import init_controller
from .const import (
    DATA_ADD_ENTRIES, DATA_CONFIG, DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_DISCONNECTED, DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE, DISPATCH_ZONE_UPDATE)

_LOGGER = logging.getLogger(__name__)


class DiscoveryService(pizone.Listener):
    """Discovery data and interfacing with pizone library."""

    def __init__(self, hass):
        """Initialise discovery service."""
        super().__init__()
        self.hass = hass
        self.controllers = {}  # type: Dict[str, pizone.Controller]
        self.controller_ready = Event()

        self.pi_disco = None
        self.stop_listener = None

        async def _controller_discovered(ctrl: pizone.Controller):
            assert ctrl.device_uid not in self.controllers, \
                "discovered device that already exists"
            _LOGGER.debug("Controller discovered uid=%s", ctrl.device_uid)

            conf = self.hass.data.get(DATA_CONFIG)  # type: ConfigType

            # Filter out any entities excluded in the config file
            if conf and ctrl.device_uid in conf[CONF_EXCLUDE]:
                _LOGGER.info(
                    "Controller UID=%s ignored as excluded.",
                    ctrl.device_uid)
                return

            self.controllers[ctrl.device_uid] = ctrl
            self.controller_ready.set()

            # This will be present if the component is configured.
            # otherwise init_controller will be called when the config entry
            # is created.
            async_add_entries = self.hass.data.get(DATA_ADD_ENTRIES)
            if async_add_entries:
                init_controller(ctrl, async_add_entries)
        async_dispatcher_connect(
            hass, DISPATCH_CONTROLLER_DISCOVERED,
            _controller_discovered)

    # Listener interface
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        """Handle new controller discoverery."""
        async_dispatcher_send(
            self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    def controller_disconnected(
            self, ctrl: pizone.Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(
            self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    def controller_reconnected(self, ctrl: pizone.Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(
            self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    def controller_update(self, ctrl: pizone.Controller) -> None:
        """System update message is recieved from the controller."""
        async_dispatcher_send(
            self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

    def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
        """Zone update message is recieved from the controller."""
        async_dispatcher_send(
            self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)


async def async_start_discovery_service(hass: HomeAssistantType):
    """Set up the pizone internal discovery."""
    disco = hass.data.get(DATA_DISCOVERY_SERVICE)
    if disco:
        # Already started
        return disco

    # discovery local services
    disco = DiscoveryService(hass)
    hass.data[DATA_DISCOVERY_SERVICE] = disco

    # Start the pizone discovery service, disco is the listener
    session = aiohttp_client.async_get_clientsession(hass)
    loop = hass.loop

    disco.pi_disco = pizone.discovery(disco, loop=loop, session=session)
    await disco.pi_disco.start_discovery()

    async def shutdown_event(event):
        await async_stop_discovery_service(hass)

    disco.stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, shutdown_event)

    return disco


async def async_stop_discovery_service(hass: HomeAssistantType):
    """Stop the discovery service."""
    disco = hass.data.get(DATA_DISCOVERY_SERVICE)
    if not disco:
        return

    if disco.stop_listener:
        disco.stop_listener()
    await disco.pi_disco.close()
    if DATA_DISCOVERY_SERVICE in hass.data:
        del hass.data[DATA_DISCOVERY_SERVICE]
    if DATA_ADD_ENTRIES in hass.data:
        del hass.data[DATA_ADD_ENTRIES]
