"""Tracking for bluetooth low energy devices."""
from __future__ import annotations

import asyncio
import logging
import time
from types import MappingProxyType
from typing import Any
from uuid import UUID

from bleak import BleakClient, BleakError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_TRACK_BATTERY_INTERVAL,
    SIGNAL_BLE_DEVICE_BATTERY_UPDATE,
    SIGNAL_BLE_DEVICE_NEW,
    SIGNAL_BLE_DEVICE_SEEN,
    SIGNAL_BLE_DEVICE_UNAVAILABLE,
)

_LOGGER = logging.getLogger(__name__)

# Base UUID: 00000000-0000-1000-8000-00805F9B34FB
# Battery characteristic: 0x2a19 (https://www.bluetooth.com/specifications/gatt/characteristics/)
BATTERY_CHARACTERISTIC_UUID = UUID("00002a19-0000-1000-8000-00805f9b34fb")


def signal_battery_update(address: str) -> str:
    """Signal for a battery update."""
    return f"{SIGNAL_BLE_DEVICE_BATTERY_UPDATE}_{address}"


def signal_unavailable(address: str) -> str:
    """Signal for the device going unavailable."""
    return f"{SIGNAL_BLE_DEVICE_UNAVAILABLE}_{address}"


def signal_seen(address: str) -> str:
    """Signal for the device being seen."""
    return f"{SIGNAL_BLE_DEVICE_SEEN}_{address}"


class BLEScanner:
    """Set up the Bluetooth LE Scanner."""

    def __init__(self, hass: HomeAssistant, config: MappingProxyType[str, Any]) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.battery_update_failed: set[str] = set()
        self.last_battery_update: dict[str, float] = {}
        self.battery_track_interval = config.get(CONF_TRACK_BATTERY_INTERVAL) or 0
        self._unavailable_trackers: dict[str, CALLBACK_TYPE] = {}
        self._update_cancel: CALLBACK_TYPE | None = None

    async def _async_update_ble_battery(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        monotonic_now: float,
    ) -> None:
        """Lookup Bluetooth LE devices and update status."""
        battery = None
        address = service_info.address
        self.last_battery_update[address] = monotonic_now
        # We need one we can connect to since the tracker will
        # accept devices from non-connectable sources
        if service_info.connectable:
            device = service_info.device
        elif connectable_device := bluetooth.async_ble_device_from_address(
            self.hass, service_info.device.address, True
        ):
            device = connectable_device
        else:
            # The device can be seen by a passive tracker but we
            # don't have a route to make a connection
            return

        try:
            async with BleakClient(device) as client:
                bat_char = await client.read_gatt_char(BATTERY_CHARACTERISTIC_UUID)
                battery = ord(bat_char)
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Timeout when trying to get battery status for %s", service_info.name
            )
        # Bleak currently has a few places where checking dbus attributes
        # can raise when there is another error. We need to trap AttributeError
        # until bleak releases v0.15+ which resolves these.
        except (AttributeError, BleakError) as err:
            _LOGGER.debug("Could not read battery status: %s", err)
            # If the device does not offer battery information, there is no point in asking again later on.
            # Remove the device from the battery-tracked devices, so that their battery is not wasted
            # trying to get an unavailable information.
            self.battery_update_failed.add(address)
        if battery:
            async_dispatcher_send(self.hass, signal_battery_update(address), battery)

    @callback
    def _async_handle_unavailable(self, address: str) -> None:
        """Handle unavailable devices."""
        async_dispatcher_send(self.hass, signal_unavailable(address))
        if cancel := self._unavailable_trackers.pop(address, None):
            cancel()

    @callback
    def _async_update_ble(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        address = service_info.address
        if address not in self._unavailable_trackers:
            self._unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )
            async_dispatcher_send(self.hass, SIGNAL_BLE_DEVICE_NEW, service_info)
        else:
            async_dispatcher_send(self.hass, signal_seen(address), service_info)

        if not self.battery_track_interval or address in self.battery_update_failed:
            return

        monotonic_now = time.monotonic()
        if (
            monotonic_now
            > self.last_battery_update.get(address, 0) + self.battery_track_interval
        ):
            asyncio.create_task(
                self._async_update_ble_battery(service_info, monotonic_now)
            )

    @callback
    def async_stop(self) -> None:
        """Stop the scanner."""
        if self._update_cancel:
            self._update_cancel()
            self._update_cancel = None
        for cancel in self._unavailable_trackers.values():
            cancel()
        self._unavailable_trackers.clear()

    @callback
    def async_start(self) -> None:
        """Start the scanner."""
        self._update_cancel = bluetooth.async_register_callback(
            self.hass,
            self._async_update_ble,
            BluetoothCallbackMatcher(
                connectable=False
            ),  # We will take data from any source
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
