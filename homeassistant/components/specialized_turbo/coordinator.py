"""BLE coordinator for Specialized Turbo bikes.

Connects over BLE, subscribes to GATT notifications, parses incoming
telemetry, and pushes updates to HA entities.

TCU1 bikes only push a handful of fields via notifications. The
coordinator uses the request-read GATT pattern to poll the remaining
fields periodically.
"""

from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakClient, BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import establish_connection
from specialized_turbo import (
    CHAR_NOTIFY,
    TCU1_POLL_FIELDS,
    BLEProfile,
    TelemetrySnapshot,
    build_request,
    build_tcx_request,
    derive_key,
    detect_generation,
    get_char_notify,
    get_char_request_read,
    get_char_request_write,
    parse_message,
    parse_tcx_message,
)
from specialized_turbo.framing import is_framed_packet, unpack_tcx
from specialized_turbo.parameters import BikeParameter
from specialized_turbo.session import ProtocolSession, TCU1Session, TCXSession

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

# How often to re-poll fields via request-read (seconds).
_POLL_INTERVAL = 60

_TCX_POLL_PARAMS: tuple[BikeParameter, ...] = (
    BikeParameter.SYSTEM_STATE,
    BikeParameter.SYSTEM_RANGE_LONG,
    BikeParameter.SYSTEM_RANGE_SHORT,
    BikeParameter.SYSTEM_TEMPERATURE,
    BikeParameter.SYSTEM_CONSUMPTION,
    BikeParameter.SYSTEM_ALT,
    BikeParameter.SYSTEM_ALT_GAIN,
    BikeParameter.SYSTEM_GRADIENT,
    BikeParameter.BATTERY1_STATE_OF_CHARGE,
    BikeParameter.MOTOR_BIKE_SPEED,
    BikeParameter.MOTOR_BIKE_CADENCE,
    BikeParameter.MOTOR_POWER,
    BikeParameter.MOTOR_RIDER_INPUT_POWER,
    BikeParameter.MOTOR_TEMPERATURE,
)


class SpecializedTurboCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Manage the BLE connection and notification subscription for one bike."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
        pin: str | None = None,
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
        self._generation: BLEProfile | None = None
        self._session: ProtocolSession = TCU1Session()
        self._char_request_write: str | None = None
        self._char_request_read: str | None = None
        self._last_poll_time: float = 0
        # True once we've seen a CRC-framed (TCX) notification.
        # Some bikes advertise TCX UUIDs but send TCU1-format messages.
        self._uses_tcx_messages: bool | None = None

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_update: float | None,
    ) -> bool:
        """Return True if we need to (re)connect or re-poll fields."""
        # Detect generation early from advertisement data.
        if self._generation is None:
            gen = detect_generation(service_info.manufacturer_data)
            if gen is not None:
                self._generation = gen

        if self._client is None or not self._client.is_connected:
            return True

        # Periodically re-poll fields via request-read.
        if self._last_poll_time == 0:
            return False
        return (time.monotonic() - self._last_poll_time) >= _POLL_INTERVAL

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

        # Poll fields via request-read.  Use the message format detected
        # from notifications rather than the BLE profile, since some bikes
        # advertise TCX UUIDs but send TCU1-format messages.
        if self._client and self._client.is_connected:
            if self._uses_tcx_messages is True:
                await self._poll_tcx_fields()
            else:
                await self._poll_tcu1_fields()

    async def _ensure_connected(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak | None = None,
    ) -> None:
        """Establish BLE connection and subscribe to notifications."""
        if self._client and self._client.is_connected:
            return

        _LOGGER.debug("Connecting to Specialized Turbo at %s", self._address)

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

        char_notify = (
            get_char_notify(self._generation)
            if self._generation is not None
            else CHAR_NOTIFY
        )

        # Resolve request-read UUIDs for polling.
        if self._generation is not None:
            self._char_request_write = get_char_request_write(self._generation)
            self._char_request_read = get_char_request_read(self._generation)

        # Create protocol session based on generation.
        if self._generation == BLEProfile.TCX:
            self._session = TCXSession()  # unencrypted default
        else:
            self._session = TCU1Session()

        # Trigger pairing if PIN is provided.
        if self._pin is not None:
            try:
                await client.pair(protection_level=2)
            except NotImplementedError:
                _LOGGER.debug("Backend does not support programmatic pairing")
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Pairing failed", exc_info=True)

        # Run identification handshake for TCX bikes.
        if self._generation == BLEProfile.TCX:
            await self._identify_tcx()

        # Subscribe to telemetry notifications.
        await client.start_notify(char_notify, self._notification_handler)

    def _notification_handler(
        self, sender: BleakGATTCharacteristic | int, data: bytearray
    ) -> None:
        """Handle a BLE notification (called from Bleak's BLE thread)."""
        self.hass.loop.call_soon_threadsafe(self._handle_notification, bytes(data))

    @callback
    def _handle_notification(self, data: bytes) -> None:
        """Parse a BLE notification and push the update to HA."""
        # Auto-detect message format from the data itself.
        # CRC-framed 20-byte packets → TCX parameter ID format.
        # Anything else (e.g. 0xFF-padded) → TCU1 sender/channel format.
        framed = is_framed_packet(data)
        if self._uses_tcx_messages is None:
            self._uses_tcx_messages = framed
            _LOGGER.debug(
                "Auto-detected message format: %s", "TCX" if framed else "TCU1"
            )

        try:
            if framed:
                unpacked = self._session.unpack(data)
                msg = parse_tcx_message(unpacked)
            else:
                msg = parse_message(data)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to parse notification: %s", data.hex(), exc_info=True)
            return

        self.snapshot.update_from_message(msg)
        self.async_update_listeners()

    async def _poll_tcu1_fields(self) -> None:
        """Query all TCU1 fields via the request-read GATT pattern."""
        if (
            self._client is None
            or self._char_request_write is None
            or self._char_request_read is None
        ):
            return

        updated = False
        for sender, channel in TCU1_POLL_FIELDS:
            try:
                await self._client.write_gatt_char(
                    self._char_request_write, build_request(sender, channel)
                )
                await asyncio.sleep(0.1)
                response = await self._client.read_gatt_char(self._char_request_read)
                msg = parse_message(response)
                if msg.sender == sender and msg.channel == channel:
                    self.snapshot.update_from_message(msg)
                    updated = True
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to poll field (%02x, %02x)",
                    sender,
                    channel,
                    exc_info=True,
                )

        self._last_poll_time = time.monotonic()
        if updated:
            self.async_update_listeners()

    async def _poll_tcx_fields(self) -> None:
        """Query TCX system fields via the request-read pattern."""
        if (
            self._client is None
            or self._char_request_write is None
            or self._char_request_read is None
        ):
            return

        updated = False
        for param in _TCX_POLL_PARAMS:
            try:
                request = build_tcx_request(int(param))
                packed = self._session.pack(request)
                await self._client.write_gatt_char(self._char_request_write, packed)
                await asyncio.sleep(0.1)
                response = await self._client.read_gatt_char(self._char_request_read)
                unpacked = self._session.unpack(response)
                msg = parse_tcx_message(unpacked)
                self.snapshot.update_from_message(msg)
                updated = True
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Failed to poll TCX param %d", int(param), exc_info=True)

        self._last_poll_time = time.monotonic()
        if updated:
            self.async_update_listeners()

    async def _identify_tcx(self) -> None:
        """Run the TCX identification handshake to exchange encryption keys.

        Executes a short 3-step request-read sequence. Step 3 returns the
        encryption key material.  On success, replaces self._session with
        an encrypted TCXSession.  On failure, keeps the unencrypted session.
        """
        if (
            self._client is None
            or self._char_request_write is None
            or self._char_request_read is None
        ):
            return

        steps = [
            BikeParameter.SYSTEM_GET_NEW_VI,
            BikeParameter.SYSTEM_STATE,
            BikeParameter.BATTERY1_FIRMWARE,
        ]

        key_response: bytes | None = None

        try:
            for param in steps:
                request = build_tcx_request(int(param))
                await self._client.write_gatt_char(self._char_request_write, request)
                await asyncio.sleep(0.15)
                response = await self._client.read_gatt_char(self._char_request_read)
                if param == BikeParameter.BATTERY1_FIRMWARE:
                    key_response = bytes(response)
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "TCX identification handshake failed, using unencrypted session",
                exc_info=True,
            )
            return

        if key_response is None or len(key_response) < 4:
            return

        # Extract the base64 key string from the response payload.
        payload = key_response
        if is_framed_packet(payload):
            payload = unpack_tcx(payload)
        # Skip 2-byte param ID prefix.
        key_data = payload[2:]
        # Strip trailing zero padding.
        key_data = key_data.rstrip(b"\x00")

        if len(key_data) == 0:
            _LOGGER.debug(
                "Encryption key response was empty — bike may not require encryption"
            )
            return

        try:
            key_str = key_data.decode("ascii")
            aes_key = derive_key(key_str)
            self._session = TCXSession(key=aes_key, iv=b"\x00" * 16)
            _LOGGER.info("TCX encryption key derived, using encrypted session")
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to derive encryption key, using unencrypted session",
                exc_info=True,
            )

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
            char_notify = (
                get_char_notify(self._generation)
                if self._generation is not None
                else CHAR_NOTIFY
            )
            try:
                await self._client.stop_notify(char_notify)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error stopping notifications", exc_info=True)
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error disconnecting", exc_info=True)
        self._client = None
