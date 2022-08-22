"""Update coordinator for the Bluetooth integration."""
from __future__ import annotations

import logging
import time

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from . import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
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
        self.name: str | None = None
        self.address = address
        self.connectable = connectable
        self._cancel_track_unavailable: CALLBACK_TYPE | None = None
        self._cancel_bluetooth_advertisements: CALLBACK_TYPE | None = None
        self._present = False
        self.mode = mode
        self.last_seen = 0.0

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start the data updater."""
        self._async_start()

        @callback
        def _async_cancel() -> None:
            self._async_stop()

        return _async_cancel

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._present

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
    def _async_handle_unavailable(self, address: str) -> None:
        """Handle the device going unavailable."""
        self._present = False

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.last_seen = time.monotonic()
        self.name = service_info.name
        self._present = True
