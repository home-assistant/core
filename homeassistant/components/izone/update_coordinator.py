"""Data update coordinator for iZone."""
from collections.abc import Callable
import logging
from typing import Any

import pizone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_RECONNECTED,
    IZONE,
)

_LOGGER = logging.getLogger(__name__)


class ControllerUpdateCoordinator:
    """Coordinate updates for a controller. This works similarly to homeassistant.helpers.update_coordinator.DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ctrl: pizone.Controller,
    ) -> None:
        """Initialise the update coordinator."""
        self._entry = entry
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
        def controller_disconnected(ctrl: pizone.Controller, _: Exception) -> None:
            """Disconnected from controller."""
            _LOGGER.info(
                "Controller '%s' disconnected",
                self._controller.device_uid,
                exc_info=True,
            )
            if ctrl is not self._controller:
                return
            self._set_available(False)

        self._entry.async_on_unload(
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

        self._entry.async_on_unload(
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
