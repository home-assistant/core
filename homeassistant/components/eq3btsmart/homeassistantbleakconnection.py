"""
Bleak connection backend.

This creates a new event loop that is used to integrate bleak's
asyncio functions to synchronous architecture of python-eq3bt.
"""
from __future__ import annotations

import asyncio
import codecs
import logging

from bleak import BleakClient, BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
import eq3bt as eq3

from homeassistant import core
from homeassistant.components import bluetooth

DEFAULT_TIMEOUT = 1

_LOGGER = logging.getLogger(__name__)


class HomeAssistantBleakConnection:
    """Representation of a BTLE Connection."""

    def __init__(self, mac, iface):
        """Initialize the connection."""
        self._conn: BleakClient | None = None
        self._mac = mac
        self._hass = core.async_get_hass()
        self._callbacks = {}
        self._notifyevent = asyncio.Event()
        self._notification_handle = None
        self._scanner = bluetooth.async_get_scanner(self._hass)

        self._loop = self._hass.loop

    def get_client(self) -> BleakClient:
        """Get the Bluetooth device from hass."""
        device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self._hass, self._mac, connectable=False
        )
        if device is None:
            eq3.BackendException(
                f"Could not find Eq3 bt Smart with address {self._mac}"
            )
        assert device is not None
        return BleakClient(device)

    async def connect_and_start_notify(self) -> None:
        """Async Function to connect to the device and start the notify."""
        assert self._conn is not None
        await self._conn.connect()
        await self._conn.start_notify(
            self._notification_handle - 1, self.on_notification
        )

    def __enter__(self):
        """
        Context manager __enter__ for connecting the device.

        :rtype: BTLEConnection
        :return:
        """
        _LOGGER.debug("Trying to connect to %s", self._mac)

        self._conn = self.get_client()

        try:
            asyncio.run_coroutine_threadsafe(
                self.connect_and_start_notify(), self._loop
            ).result()
        except BleakError as ex:
            _LOGGER.debug(
                "Unable to connect to the device %s, retrying: %s", self._mac, ex
            )
            raise eq3.BackendException(
                "unable to connect to device using bleak"
            ) from ex
        _LOGGER.debug("Connected to %s", self._mac)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the Connection to the Bleak client."""
        if self._conn:
            asyncio.run_coroutine_threadsafe(
                self._conn.disconnect(), self._loop
            ).result()
            self._conn = None

    async def on_notification(self, gatt: BleakGATTCharacteristic, data: bytearray):
        """Handle Callback from a Bluetooth (GATT) request."""
        # The notification handles are off-by-one compared to gattlib and bluepy
        handle = gatt.handle + 1
        _LOGGER.debug(
            "Got notification from %s: %s", handle, codecs.encode(data, "hex")
        )
        self._notifyevent.set()

        if handle in self._callbacks:
            self._callbacks[handle](data)

    @property
    def mac(self):
        """Return the MAC address of the connected device."""
        return self._mac

    def set_callback(self, handle, function):
        """Set the callback for a Notification handle. It will be called with the parameter data, which is binary."""
        self._notification_handle = handle
        self._callbacks[handle] = function

    async def wait_for_response(self, timeout):
        """Wait until the notifyevent was set or the timeout expires."""
        try:
            await asyncio.wait_for(self._notifyevent.wait(), timeout)
        except asyncio.TimeoutError:
            _LOGGER.debug("Exception on wait")

    async def write_and_handle_response(self, handle, value, timeout) -> None:
        """Write to the bleak client and await the response if a timeout is set."""
        assert self._conn is not None
        await self._conn.write_gatt_char(handle - 1, value)
        if timeout:
            _LOGGER.debug("Waiting for notifications for %s", timeout)
            await self.wait_for_response(timeout)

    def make_request(self, handle, value, timeout=DEFAULT_TIMEOUT, with_response=True):
        """Write a GATT Command without callback - not utf-8."""
        try:
            with self:
                _LOGGER.debug(
                    "Writing %s to %s",
                    codecs.encode(value, "hex"),
                    handle,
                )
                self._notifyevent.clear()

                asyncio.run_coroutine_threadsafe(
                    self.write_and_handle_response(handle, value, timeout), self._loop
                ).result()

        except BleakError as ex:
            _LOGGER.debug("Got exception from bleak while making a request: %s", ex)
            raise eq3.BackendException("Exception on write using bleak") from ex
