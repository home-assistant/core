"""Contains a GoDice factory function and connection handling code."""

import asyncio
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakError,
    close_stale_connections,
    establish_connection,
)
import godice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def create_dice(hass: HomeAssistant, entry: ConfigEntry):
    """Create a Dice representative object."""
    return DiceProxy(hass, entry)


class DiceDelegate:
    """Delegate method calls to GoDice."""

    async def get_color(self):
        """Get Dice color."""
        return await self._dice.get_color()

    async def get_battery_level(self):
        """Get Dice battery level."""
        return await self._dice.get_battery_level()

    async def subscribe_number_notification(self, callback):
        """Subscribe for receiving notifications with new numbers when Dice is rolled."""
        await self._dice.subscribe_number_notification(callback)

    async def pulse_led(self, *args, **kwargs):
        """Pulse built-in LEDs."""
        await self._dice.pulse_led(*args, **kwargs)


class NoopDice:
    """No-op Dice impl used when GoDice is disconnected."""

    async def connect(self, disconnect_cb):
        """Connect."""

    async def disconnect(self):
        """Disconnect."""

    async def get_color(self):
        """Get Dice color."""

    async def get_battery_level(self):
        """Get Dice battery level."""

    async def subscribe_number_notification(self, _callback):
        """Subscribe for receiving notifications with new numbers when Dice is rolled."""

    async def pulse_led(self, *args, **kwargs):
        """Pulse built-in LEDs."""


class DiceProxy(DiceDelegate):
    """Proxy between HA and Dice, manages connection establishment."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init connection data."""
        self._mac = entry.data["address"]
        self._hass = hass
        self._dice = NoopDice()
        self._conn_lock = asyncio.Lock()
        self._bledev: BLEDevice | None = None
        self._bledev_upd_cancel = bluetooth.async_register_callback(
            hass,
            self._upd_bledev,
            bluetooth.BluetoothCallbackMatcher({bluetooth.match.ADDRESS: self._mac}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        self._disconnect_cb = None
        self._client = None
        self._disconnect_handler = self._on_connection_lost_while_connecting_handler

    async def connect(self, disconnect_cb):
        """Connect to the Dice."""
        async with self._conn_lock:
            _LOGGER.debug("Connecting")
            self._disconnect_cb = disconnect_cb
            self._bledev = self._bledev or bluetooth.async_ble_device_from_address(
                self._hass, self._mac
            )
            try:
                self._client = await establish_connection(
                    client_class=BleakClient,
                    device=self._bledev,
                    name=self._mac,
                    disconnected_callback=self._on_disconnected_handler,
                    max_attempts=3,
                    use_services_cache=True,
                )
                dice = godice.create(self._client, godice.Shell.D6)
                await dice.connect()
                self._dice = dice
                self._disconnect_handler = (
                    self._on_connection_lost_after_connected_handler
                )
                _LOGGER.debug("Connection completed")
            except BleakError as e:
                _LOGGER.debug("Connection attempts timed out")
                await close_stale_connections(self._bledev)
                raise e

    async def disconnect(self):
        """Disconnect from the Dice."""
        async with self._conn_lock:
            self._disconnect_handler = self._on_disconnected_by_request_handler
            await self._dice.disconnect()
            await close_stale_connections(self._bledev)

    def _upd_bledev(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ):
        self._bledev = service_info.device

    def _on_connection_lost_while_connecting_handler(self, _data):
        _LOGGER.debug("Connection lost while connecting. Reconnection is skipped")

    def _on_connection_lost_after_connected_handler(self, data):
        _LOGGER.debug("Connection lost")
        self._disconnect_handler = self._on_disconnected_noop_handler
        self._hass.create_task(self._disconnect_cb(data, False))

    def _on_disconnected_by_request_handler(self, data):
        _LOGGER.debug("Disconnected by request")
        self._disconnect_handler = self._on_disconnected_noop_handler
        self._hass.create_task(self._disconnect_cb(data, True))

    def _on_disconnected_noop_handler(self, _data):
        _LOGGER.debug("Extra disconnect event. Skipping handling")

    def _on_disconnected_handler(self, data):
        _LOGGER.debug("Disconnect event received")
        self._dice = NoopDice()
        self._disconnect_handler(data)
