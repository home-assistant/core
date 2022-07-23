"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any, cast

from bleak.backends.device import BLEDevice
import switchbot
from switchbot import parse_advertisement_data

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import CONF_RETRY_COUNT

_LOGGER = logging.getLogger(__name__)


def flatten_sensors_data(sensor):
    """Deconstruct SwitchBot library temp object C/Fº readings from dictionary."""
    if "temp" in sensor["data"]:
        sensor["data"]["temperature"] = sensor["data"]["temp"]["c"]

    return sensor


class SwitchbotCoordinator:
    """Class to manage fetching switchbot data."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: BLEDevice,
        device: switchbot.SwitchbotDevice,
        common_options: dict[str, int],
    ) -> None:
        """Initialize global switchbot data updater."""
        self.hass = hass
        self.ble_device = ble_device
        self.device = device
        self.common_options = common_options
        self.data: dict[str, Any] = {}
        self._listeners: list[Callable[[], None]] = []
        self.ready_event = asyncio.Event()
        self.available = False

    @property
    def retry_count(self) -> int:
        """Return retry count."""
        return self.common_options[CONF_RETRY_COUNT]

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfo,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.available = True
        discovery_info_bleak = cast(bluetooth.BluetoothServiceInfoBleak, service_info)
        if adv := parse_advertisement_data(
            discovery_info_bleak.device, discovery_info_bleak.advertisement
        ):
            self.data = flatten_sensors_data(adv.data)
            if "modelName" in self.data:
                self.ready_event.set()
            _LOGGER.debug("%s: Switchbot data: %s", self.ble_device.address, self.data)
            self.device.update_from_advertisement(adv)
        self._async_call_listeners()

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=55)
        except asyncio.TimeoutError:
            return False
        return True

    def _async_call_listeners(self) -> None:
        for listener in self._listeners:
            listener()

    def _async_mark_unavailable(self, address: str) -> None:
        self.available = False
        self._async_call_listeners()

    def async_start(self) -> CALLBACK_TYPE:
        """Start the data updater."""
        cancels = [
            bluetooth.async_register_callback(
                self.hass,
                self._async_handle_bluetooth_event,
                bluetooth.BluetoothCallbackMatcher(address=self.ble_device.address),
            ),
            bluetooth.async_track_unavailable(
                self.hass, self._async_mark_unavailable, self.ble_device.address
            ),
        ]

        @callback
        def _cancel() -> None:
            for cancel in cancels:
                cancel()

        return _cancel

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.remove(update_callback)

        self._listeners.append(update_callback)
        return remove_listener
