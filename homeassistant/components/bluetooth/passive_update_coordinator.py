"""The Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ._coordinator import BasePassiveBluetoothCoordinator


class PassiveBluetoothDataUpdateCoordinator(BasePassiveBluetoothCoordinator):
    """Class to manage passive bluetooth advertisements.

    This coordinator is responsible for dispatching the bluetooth data
    and tracking devices.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
    ) -> None:
        """Initialize PassiveBluetoothDataUpdateCoordinator."""
        super().__init__(hass, logger, address)
        self._listeners: list[Callable[[], None]] = []

    def _async_call_listeners(self) -> None:
        for listener in self._listeners:
            listener()

    @callback
    def _async_handle_unavailable(self, address: str) -> None:
        """Handle the device going unavailable."""
        super()._async_handle_unavailable(address)
        self._async_call_listeners()

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start the data updater."""
        self._async_start()

        @callback
        def _async_cancel() -> None:
            self._async_stop()

        return _async_cancel

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.remove(update_callback)

        self._listeners.append(update_callback)
        return remove_listener


class PassiveBluetoothCoordinatorEntity(CoordinatorEntity):
    """A class for entities using DataUpdateCoordinator."""

    coordinator: PassiveBluetoothDataUpdateCoordinator

    async def async_update(self) -> None:
        """All updates are passive."""
