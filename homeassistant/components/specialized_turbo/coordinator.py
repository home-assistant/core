"""BLE coordinator for Specialized Turbo bikes.

Connects over BLE, subscribes to GATT notifications, and delegates
protocol-specific parsing, polling, and identification to the
specialized-turbo library.
"""

from __future__ import annotations

import logging

from bleak import BleakClient, BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection
from specialized_turbo import (
    CHAR_NOTIFY,
    BLEProfile,
    ProtocolSession,
    TCU1Session,
    TelemetrySnapshot,
    detect_generation,
    get_char_notify,
    get_char_request_read,
    get_char_request_write,
    identify_tcx,
    is_framed_packet,
    parse_notification,
    poll_tcu1,
    poll_tcx,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

# How often to re-poll fields via request-read (seconds).
_POLL_INTERVAL = 60


class SpecializedTurboCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Manage the BLE connection and notification subscription for one bike."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
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
        self.snapshot = TelemetrySnapshot()
        self._client: BleakClient | None = None
        self._was_unavailable = False
        self._generation: BLEProfile | None = None
        self._session: ProtocolSession = TCU1Session()
        self._char_notify: str = CHAR_NOTIFY
        self._char_request_write: str | None = None
        self._char_request_read: str | None = None
        self._uses_tcx_messages: bool | None = None
        self._logged_unresolved_chars = False

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_update: float | None,
    ) -> bool:
        """Return True if we need to (re)connect or re-poll fields."""
        if self._generation is None:
            gen = detect_generation(service_info.manufacturer_data)
            if gen is not None:
                self._generation = gen

        if self._client is None or not self._client.is_connected:
            return True

        return (
            seconds_since_last_update is None
            or seconds_since_last_update >= _POLL_INTERVAL
        )

    async def _do_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak | None = None,
    ) -> None:
        """Connect to the bike and poll fields via request-read."""
        try:
            await self._ensure_connected(service_info)
        except BleakError:
            self._client = None
            raise

        # Derive char UUIDs if generation was detected (from advertisements)
        # after the initial connection was made without it.
        if self._generation is not None and self._char_request_write is None:
            self._char_request_write = get_char_request_write(self._generation)
            self._char_request_read = get_char_request_read(self._generation)

        if (
            self._client is None
            or not self._client.is_connected
            or self._char_request_write is None
            or self._char_request_read is None
        ):
            if (
                self._client is not None
                and self._client.is_connected
                and self._char_request_write is None
                and not self._logged_unresolved_chars
            ):
                _LOGGER.warning(
                    (
                        "Connected to Specialized Turbo at %s but could not"
                        " determine the bike generation from advertisements;"
                        " no telemetry will be polled until the generation is"
                        " detected"
                    ),
                    self._address,
                )
                self._logged_unresolved_chars = True
            return

        self._logged_unresolved_chars = False

        if self._uses_tcx_messages is True:
            await poll_tcx(
                self._client,
                self._session,
                self._char_request_write,
                self._char_request_read,
                self.snapshot,
            )
        else:
            await poll_tcu1(
                self._client,
                self._char_request_write,
                self._char_request_read,
                self.snapshot,
            )

    async def _ensure_connected(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak | None = None,
    ) -> None:
        """Establish BLE connection and subscribe to notifications."""
        if self._client and self._client.is_connected:
            return

        ble_device = (
            service_info.device
            if service_info is not None
            else bluetooth.async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
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

        if self._generation is not None:
            self._char_notify = get_char_notify(self._generation)
            self._char_request_write = get_char_request_write(self._generation)
            self._char_request_read = get_char_request_read(self._generation)

        if (
            self._generation == BLEProfile.TCX
            and self._char_request_write is not None
            and self._char_request_read is not None
        ):
            self._session = await identify_tcx(
                client, self._char_request_write, self._char_request_read
            )
        else:
            self._session = TCU1Session()

        await client.start_notify(self._char_notify, self._notification_handler)

    def _notification_handler(
        self, sender: BleakGATTCharacteristic | int, data: bytearray
    ) -> None:
        """Handle a BLE notification (called from Bleak's BLE thread)."""
        self.hass.loop.call_soon_threadsafe(self._handle_notification, bytes(data))

    @callback
    def _handle_notification(self, data: bytes) -> None:
        """Parse a BLE notification and push the update to HA."""
        if self._uses_tcx_messages is None:
            self._uses_tcx_messages = is_framed_packet(data)

        try:
            msg = parse_notification(self._session, data)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to parse notification: %s", data.hex(), exc_info=True)
            return

        self.snapshot.update_from_message(msg)
        self.async_update_listeners()

    @property
    def connected(self) -> bool:
        """Return True if the BLE client is connected."""
        return self._client is not None and self._client.is_connected

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected disconnection (called from Bleak's BLE thread)."""
        self.hass.loop.call_soon_threadsafe(self._handle_disconnect)

    @callback
    def _handle_disconnect(self) -> None:
        """Process disconnection on the HA event loop."""
        if not self._was_unavailable:
            _LOGGER.info("Disconnected from Specialized Turbo at %s", self._address)
            self._was_unavailable = True
        self._client = None
        self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Clean up BLE connection on unload."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(self._char_notify)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error stopping notifications", exc_info=True)
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error disconnecting", exc_info=True)
        self._client = None
