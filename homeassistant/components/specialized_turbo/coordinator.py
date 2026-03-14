"""BLE coordinator for Specialized Turbo bikes.

Connects over BLE, subscribes to GATT notifications, parses incoming
telemetry, and pushes updates to HA entities.
"""

from __future__ import annotations

import logging

from bleak import BleakClient, BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection
from specialized_turbo import CHAR_NOTIFY, TelemetrySnapshot, parse_message

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


class SpecializedTurboCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Manages the BLE connection and notification subscription for one bike."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
        pin: int | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            address=address,
            needs_poll_method=self._needs_poll,
            poll_method=self._do_poll,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self._address = address
        self._pin = pin
        self.snapshot = TelemetrySnapshot()
        self._client: BleakClient | None = None
        self._was_unavailable = False

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_update: float | None,
    ) -> bool:
        """True if we need to (re)connect to the bike."""
        return self._client is None or not self._client.is_connected

    async def _do_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak | None = None,
    ) -> None:
        """Connect to the bike and subscribe to notifications."""
        try:
            await self._ensure_connected()
        except BleakError as err:
            _LOGGER.debug("BLE connection unavailable for %s: %s", self._address, err)
            self._client = None

    async def _ensure_connected(self) -> None:
        """Establish BLE connection and subscribe to notifications."""
        if self._client and self._client.is_connected:
            return

        _LOGGER.debug("Connecting to Specialized Turbo at %s", self._address)

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )

        if ble_device is None:
            if not self._was_unavailable:
                _LOGGER.info("Specialized Turbo at %s is unavailable", self._address)
                self._was_unavailable = True
            return

        client = await establish_connection(
            BleakClient,
            ble_device,
            self._address,
            disconnected_callback=self._on_disconnect,
        )
        self._client = client

        if self._was_unavailable:
            _LOGGER.info("Specialized Turbo at %s is available again", self._address)
            self._was_unavailable = False

        # Trigger pairing if PIN is provided
        if self._pin is not None:
            try:
                await client.pair(protection_level=2)
                _LOGGER.info("Paired with PIN")
            except NotImplementedError:
                _LOGGER.debug("Backend does not support programmatic pairing")
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Pairing failed", exc_info=True)

        # Subscribe to telemetry notifications
        await client.start_notify(CHAR_NOTIFY, self._notification_handler)
        _LOGGER.info("Subscribed to telemetry notifications")

    def _notification_handler(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Parse a BLE notification and push the update to HA."""
        try:
            msg = parse_message(data)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to parse notification: %s", data.hex(), exc_info=True)
            return

        self.snapshot.update_from_message(msg)

        if msg.field_name:
            _LOGGER.debug("%s = %s %s", msg.field_name, msg.converted_value, msg.unit)

        # Push the update to HA — schedule on the event loop since
        # bleak notification callbacks may come from a background thread.
        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    @property
    def connected(self) -> bool:
        """Return True if the BLE client is connected."""
        return self._client is not None and self._client.is_connected

    @callback
    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected disconnection."""
        if not self._was_unavailable:
            _LOGGER.info("Disconnected from Specialized Turbo at %s", self._address)
            self._was_unavailable = True
        self._client = None
        # Notify listeners so entities mark themselves unavailable
        self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Clean up BLE connection on unload."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(CHAR_NOTIFY)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error stopping notifications", exc_info=True)
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error disconnecting", exc_info=True)
        self._client = None
