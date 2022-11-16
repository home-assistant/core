"""Update coordinator for the Bluetooth integration."""
from __future__ import annotations

from abc import abstractmethod
import logging
from typing import cast

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from . import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_address_present,
    async_last_service_info,
    async_register_callback,
    async_track_unavailable,
)


class BasePassiveBluetoothCoordinator:
    """Base class for passive bluetooth coordinator for bluetooth advertisements.

    The coordinator is responsible for tracking devices.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        address: str,
        mode: BluetoothScanningMode,
        connectable: bool,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.logger = logger
        self.address = address
        self.connectable = connectable
        self._cancel_track_unavailable: CALLBACK_TYPE | None = None
        self._cancel_bluetooth_advertisements: CALLBACK_TYPE | None = None
        self.mode = mode
        self._last_unavailable_time = 0.0
        self._last_name = address

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start the data updater."""
        self._async_start()

        @callback
        def _async_cancel() -> None:
            self._async_stop()

        return _async_cancel

    @callback
    @abstractmethod
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a bluetooth event."""

    @property
    def name(self) -> str:
        """Return last known name of the device."""
        if service_info := async_last_service_info(
            self.hass, self.address, self.connectable
        ):
            return cast(str, service_info.name)  # for compat this can be a pyobjc
        return self._last_name

    @property
    def last_seen(self) -> float:
        """Return the last time the device was seen."""
        # If the device is unavailable it will not have a service
        # info and fall through below.
        if service_info := async_last_service_info(
            self.hass, self.address, self.connectable
        ):
            return service_info.time
        # This is the time from the last advertisement that
        # was set when the unavailable callback was called.
        return self._last_unavailable_time

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return async_address_present(self.hass, self.address, self.connectable)

    @callback
    def _async_start(self) -> None:
        """Start the callbacks."""
        self._cancel_bluetooth_advertisements = async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            BluetoothCallbackMatcher(
                address=self.address, connectable=self.connectable
            ),
            self.mode,
        )
        self._cancel_track_unavailable = async_track_unavailable(
            self.hass, self._async_handle_unavailable, self.address, self.connectable
        )

    @callback
    def _async_stop(self) -> None:
        """Stop the callbacks."""
        if self._cancel_bluetooth_advertisements is not None:
            self._cancel_bluetooth_advertisements()
            self._cancel_bluetooth_advertisements = None
        if self._cancel_track_unavailable is not None:
            self._cancel_track_unavailable()
            self._cancel_track_unavailable = None

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        self._last_unavailable_time = service_info.time
        self._last_name = service_info.name
