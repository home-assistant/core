"""Internal discovery service for  iZone AC."""
from collections.abc import Callable
import logging
from typing import Any

import pizone

from homeassistant.const import CONF_EXCLUDE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_POWER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    IZONE,
)

_LOGGER = logging.getLogger(__name__)


class ControllerUpdateCoordinator:
    """Coordinate updates for a controller. This works similarly to the DataUpdateCoordinator from homeassistant helpers."""

    def __init__(
        self,
        hass: HomeAssistant,
        discovery: "DiscoveryService",
        ctrl: pizone.Controller,
    ) -> None:
        """Initialise the update coordinator."""
        self._discovery = discovery
        self._controller = ctrl
        self._available_listeners: list[CALLBACK_TYPE] = []
        self._available = True
        self._device_info = DeviceInfo(
            identifiers={(IZONE, ctrl.device_uid)},
            manufacturer="IZone",
            model=ctrl.sys_type,
            name=f"iZone Controller {ctrl.device_uid}",
        )

        @callback
        def controller_disconnected(ctrl: pizone.Controller, ex: Exception) -> None:
            """Disconnected from controller."""
            _LOGGER.info(
                "Controller '%s' disconnected",
                self._controller.device_uid,
                exc_info=True,
            )
            if ctrl is not self._controller:
                return
            self._set_available(False)

        self._discovery.async_on_unload(
            async_dispatcher_connect(
                hass, DISPATCH_CONTROLLER_DISCONNECTED, controller_disconnected
            )
        )

        @callback
        def controller_reconnected(ctrl: pizone.Controller) -> None:
            """Reconnected to controller."""
            _LOGGER.info(
                "Controller '%s' reconnected",
                self._controller.device_uid,
                exc_info=True,
            )
            if ctrl is not self._controller:
                return
            self._set_available(True)

        self._discovery.async_on_unload(
            async_dispatcher_connect(
                hass, DISPATCH_CONTROLLER_RECONNECTED, controller_reconnected
            )
        )

    def _set_available(self, available: bool):
        self._available = available
        for listener in self._available_listeners:
            listener()

    @callback
    def async_add_available_listener(
        self, update_callback: CALLBACK_TYPE
    ) -> Callable[[], None]:
        """Listen for data updates."""
        self._available_listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_available_listener(update_callback)

        return remove_listener

    @callback
    def async_remove_available_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update."""
        self._available_listeners.remove(update_callback)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the controller."""
        return self._device_info

    @property
    def controller(self) -> pizone.Controller:
        """Return the pizone controller from the API."""
        return self._controller

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_request_refresh(self) -> None:
        """Request a refresh. This gets passed off to the controller and batched."""
        await self._controller.refresh()


ControllerAddedListener = Callable[[ControllerUpdateCoordinator], None]


class ControllerCoordinatorEntity(Entity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(self, coordinator: ControllerUpdateCoordinator) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator

    @property
    def controller(self) -> pizone.Controller:
        """Get the controller."""
        return self.coordinator.controller

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available

    @callback
    def add_dispatcher_update(self, dispatch_message: str, *args: list[Any]) -> None:
        """Add a dispatch lister that triggers an update on the entity."""
        # Register for connect/disconnect/update events
        @callback
        def handle_dispatch(*uargs: list[Any]) -> None:
            """Handle controller data updates."""
            if uargs != args:
                return
            self._handle_coordinator_update()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, dispatch_message, handle_dispatch)
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_available_listener(
                self._handle_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        await self.coordinator.async_request_refresh()


class DiscoveryService(pizone.Listener):
    """Discovery data and interfacing with pizone library."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise discovery service."""
        super().__init__()
        self._controller_discovered_listeners: list[ControllerAddedListener] = []
        self._unload_listeners: list[CALLBACK_TYPE] = []
        self._controllers: dict[str, ControllerUpdateCoordinator] = {}

        self.hass = hass
        hass.data[DATA_DISCOVERY_SERVICE] = self

        @callback
        def controller_discovered(ctrl: pizone.Controller) -> None:
            """Discovered new controller."""
            conf = hass.data.get(DATA_CONFIG)

            # Filter out any entities excluded in the config file
            if conf and CONF_EXCLUDE in conf and ctrl.device_uid in conf[CONF_EXCLUDE]:
                _LOGGER.info("Controller UID=%s ignored as excluded", ctrl.device_uid)
                return
            if self._controllers.get(ctrl.device_uid) is not None:
                _LOGGER.error(
                    'Attempt to add controller "%s" when already known', ctrl.device_uid
                )
                return
            _LOGGER.info("Controller UID=%s discovered", ctrl.device_uid)

            coord = ControllerUpdateCoordinator(self.hass, self, ctrl)
            self._controllers[ctrl.device_uid] = coord

            for listener in self._controller_discovered_listeners:
                listener(coord)

        self.async_on_unload(
            async_dispatcher_connect(
                hass, DISPATCH_CONTROLLER_DISCOVERED, controller_discovered
            )
        )

        # Start the pizone discovery service, disco is the listener
        session = aiohttp_client.async_get_clientsession(hass)
        self.pi_disco = pizone.discovery(self, session=session)

    async def unload(self) -> None:
        """Unload the discovery service."""
        for listener in self._unload_listeners:
            listener()
        await self.pi_disco.close()

    @callback
    def async_on_unload(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Add listener for the service being unloaded."""
        self._unload_listeners.append(listener)

        @callback
        def remove_listener() -> None:
            """Remove unload listener."""
            self._unload_listeners.remove(listener)

        return remove_listener

    @callback
    def async_add_controller_discovered_listener(
        self, listener: ControllerAddedListener
    ) -> CALLBACK_TYPE:
        """Add a listener for when a controller is discovered. This will be called with all current controllers before this function returns."""
        self._controller_discovered_listeners.append(listener)

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_controller_discovered_listener(listener)

        for controller in self._controllers.values():
            listener(controller)

        return remove_listener

    @callback
    def async_remove_controller_discovered_listener(
        self, listener: ControllerAddedListener
    ) -> None:
        """Remove listener for controller discovered."""
        self._controller_discovered_listeners.remove(listener)

    # Listener interface
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        """Handle new controller discoverery."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    def controller_disconnected(self, ctrl: pizone.Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    def controller_reconnected(self, ctrl: pizone.Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    def controller_update(self, ctrl: pizone.Controller) -> None:
        """System update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

    def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
        """Zone update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)

    def power_update(self, ctrl: pizone.Controller) -> None:
        """Zone update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_POWER_UPDATE, ctrl)


async def async_start_discovery_service(hass: HomeAssistant):
    """Set up the pizone internal discovery."""
    if disco := hass.data.get(DATA_DISCOVERY_SERVICE):
        # Already started
        return disco

    # discovery local services
    disco = DiscoveryService(hass)

    await disco.pi_disco.start_discovery()

    async def shutdown_event(event):
        await async_stop_discovery_service(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_event)

    return disco


async def async_stop_discovery_service(hass: HomeAssistant):
    """Stop the discovery service."""
    if not (disco := hass.data.get(DATA_DISCOVERY_SERVICE)):
        return

    await disco.unload()
    del hass.data[DATA_DISCOVERY_SERVICE]
