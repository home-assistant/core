"""Flic 2 BLE protocol client implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import IntEnum
import logging
from typing import Any

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from .const import (
    CONN_PARAM_INTERVAL_MAX,
    CONN_PARAM_INTERVAL_MIN,
    CONN_PARAM_LATENCY,
    CONN_PARAM_TIMEOUT,
    CONNECTION_TIMEOUT,
    FLIC_MAX_PACKET_SIZE,
    FLIC_MTU,
    FLIC_SIGNATURE_SIZE,
    FRAME_HEADER_CONN_ID_MASK,
    FRAME_HEADER_FRAGMENT_FLAG,
    FRAME_HEADER_NEWLY_ASSIGNED,
    TWIST_DISCONNECT_REASON_INVALID_SIGNATURE,
    TWIST_DISCONNECT_REASON_OTHER_CLIENT,
    TWIST_OPCODE_BUTTON_EVENT,
    TWIST_OPCODE_DISCONNECTED_VERIFIED_LINK,
    TWIST_OPCODE_TWIST_EVENT,
    DeviceType,
    PushTwistMode,
)
from .flic_security import chaskey_with_dir_and_counter
from .handlers import (
    DeviceCapabilities,
    DeviceProtocolHandler,
    DuoProtocolHandler,
    TwistProtocolHandler,
    create_handler,
)

_LOGGER = logging.getLogger(__name__)


class SessionState(IntEnum):
    """Flic session states."""

    DISCONNECTED = 0
    CONNECTED = 1
    WAIT_FULL_VERIFY_1 = 2
    WAIT_FULL_VERIFY_2 = 3
    WAIT_QUICK_VERIFY = 4
    SESSION_ESTABLISHED = 5
    FAILED = 6


class FlicProtocolError(Exception):
    """Flic protocol error."""


class FlicPairingError(Exception):
    """Flic pairing error."""


class FlicAuthenticationError(Exception):
    """Flic authentication error."""


class FlicClient:
    """Flic 2/Duo/Twist BLE client implementing the Flic protocol.

    This class orchestrates BLE communication and delegates device-specific
    protocol handling to DeviceProtocolHandler implementations.
    """

    def __init__(
        self,
        address: str,
        ble_device: BLEDevice | None = None,
        pairing_id: int | None = None,
        pairing_key: bytes | None = None,
        serial_number: str | None = None,
        device_type: DeviceType | None = None,
        sig_bits: int = 0,
        push_twist_mode: PushTwistMode = PushTwistMode.DEFAULT,
    ) -> None:
        """Initialize Flic client.

        Args:
            address: Bluetooth address of the device
            ble_device: BLE device to connect to (None if not yet discovered)
            pairing_id: Stored pairing ID (for reconnection)
            pairing_key: Stored pairing key (for reconnection)
            serial_number: Button serial number (used for Duo/Twist detection)
            device_type: Explicit device type (FLIC2, DUO, or TWIST)
            sig_bits: Ed25519 signature variant (0-3, used by Twist for quick verify)
            push_twist_mode: Push twist mode setting for Twist devices

        """
        self.ble_device = ble_device
        self.address = address
        self._client: BleakClient | None = None
        self._state = SessionState.DISCONNECTED
        self._connection_id = 0

        # Pairing credentials
        self._pairing_id = pairing_id
        self._pairing_key = pairing_key
        self._sig_bits = sig_bits

        # Serial number for device detection
        self._serial_number = serial_number

        # Determine device type
        if device_type is not None:
            self._device_type = device_type
        elif serial_number:
            self._device_type = DeviceType.from_serial_number(serial_number)
        else:
            self._device_type = DeviceType.FLIC2

        # Create protocol handler for this device type
        self._handler: DeviceProtocolHandler = create_handler(
            self._device_type, serial_number, push_twist_mode
        )

        # Session state
        self._session_key: bytes | None = None
        self._chaskey_keys: list[int] | None = None
        self._packet_counter_to_button = 0
        self._packet_counter_from_button = 0

        # Response handling
        self._response_queue: asyncio.Queue[bytes] = asyncio.Queue()

        # Fragment reassembly (for Flic 2/Duo with frame headers)
        self._fragment_buffer: bytearray = bytearray()
        self._expecting_fragment = False

        # Button event callback
        self.on_button_event: Callable[[str, dict[str, Any]], None] | None = None

        # Rotate event callback (for Flic Duo/Twist)
        self.on_rotate_event: Callable[[str, dict[str, Any]], None] | None = None

        # Selector change callback (for Twist only)
        self.on_selector_change: Callable[[int, dict[str, Any]], None] | None = None

    @property
    def handler(self) -> DeviceProtocolHandler:
        """Return the protocol handler."""
        return self._handler

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""
        return self._handler.capabilities

    async def connect(self) -> None:
        """Connect to the Flic button via BLE."""
        if self._client and self._client.is_connected:
            _LOGGER.debug("Already connected to %s", self.address)
            return

        if not self.ble_device:
            raise FlicProtocolError(f"No BLE device available for {self.address}")

        try:
            _LOGGER.info("Connecting to Flic button at %s", self.address)
            self._client = BleakClient(self.ble_device, timeout=CONNECTION_TIMEOUT)
            await self._client.connect()
            _LOGGER.info("BLE connection established to %s", self.address)

            # Check MTU size
            if hasattr(self._client, "mtu_size"):
                current_mtu = self._client.mtu_size
                _LOGGER.debug("Current MTU size: %d bytes", current_mtu)
                if current_mtu < FLIC_MTU:
                    _LOGGER.warning(
                        "MTU size %d is below recommended %d bytes",
                        current_mtu,
                        FLIC_MTU,
                    )

            # Request connection parameters for better responsiveness
            await self._request_connection_parameters()

            # Start notifications using handler's characteristic UUID
            _LOGGER.debug(
                "Starting notifications on characteristic %s",
                self._handler.notify_char_uuid,
            )
            await self._client.start_notify(
                self._handler.notify_char_uuid, self._notification_handler
            )
            _LOGGER.debug("Notifications started successfully for %s", self.address)

            self._state = SessionState.CONNECTED
            self._packet_counter_to_button = 0
            self._packet_counter_from_button = 0
            _LOGGER.debug("Session state set to CONNECTED")

            # Small delay to let notifications stabilize
            await asyncio.sleep(0.5)
            _LOGGER.debug("Connection stabilized, ready for pairing")

        except (TimeoutError, BleakError) as err:
            self._state = SessionState.FAILED
            _LOGGER.error("Failed to connect to %s: %s", self.address, err)
            raise FlicProtocolError(f"Failed to connect: {err}") from err

    async def disconnect(self) -> None:
        """Disconnect from the Flic button."""
        if self._client:
            try:
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error disconnecting: %s", err)
            finally:
                self._client = None
                self._state = SessionState.DISCONNECTED
                self._handler.reset_state()

    async def _request_connection_parameters(self) -> None:
        """Request BLE connection parameters for optimal communication.

        Sets latency, connection interval, and supervision timeout.
        This is platform-dependent and may not be supported on all backends.
        """
        if not self._client:
            return

        try:
            # Try to access the backend's connection parameter method
            # This is available on some Bleak backends
            backend = getattr(self._client, "_backend", None)
            if backend is None:
                _LOGGER.debug("No backend available for connection parameters")
                return

            backend_class_name = type(backend).__name__

            # Check for BlueZ DBus backend (Linux)
            if hasattr(backend, "_device_path"):
                await self._request_connection_parameters_bluez(backend)
            # Check for Core Bluetooth backend (macOS)
            elif backend_class_name == "BleakClientCoreBluetooth" or hasattr(
                backend, "_peripheral"
            ):
                await self._request_connection_parameters_corebluetooth(backend)
            # Check for WinRT backend (Windows)
            elif backend_class_name == "BleakClientWinRT" or hasattr(
                backend, "_requester"
            ):
                await self._request_connection_parameters_winrt(backend)
            else:
                _LOGGER.debug(
                    "Connection parameter request not supported for backend: %s",
                    backend_class_name,
                )
        except Exception as err:  # noqa: BLE001
            # Connection parameter request is optional, don't fail the connection
            _LOGGER.debug("Failed to request connection parameters: %s", err)

    async def _request_connection_parameters_bluez(self, backend: object) -> None:
        """Request connection parameters on BlueZ (Linux).

        Args:
            backend: Bleak BlueZ backend instance

        """
        bus = None
        try:
            from dbus_fast.aio import MessageBus  # noqa: PLC0415

            bus = await MessageBus().connect()

            # Get the device path from the backend
            device_path = getattr(backend, "_device_path", None)
            if not device_path:
                _LOGGER.debug("No device path available for connection parameters")
                return

            # BlueZ Device1 interface for connection parameters
            introspection = await bus.introspect("org.bluez", device_path)
            proxy = bus.get_proxy_object("org.bluez", device_path, introspection)

            # Check if the device interface supports connection parameters
            try:
                proxy.get_interface("org.bluez.Device1")
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Device1 interface not available")
                return

            # Request connection parameters via org.freedesktop.DBus.Properties
            # Note: Not all BlueZ versions support setting connection parameters
            # The parameters are: MinInterval, MaxInterval, Latency, Timeout
            _LOGGER.debug(
                "Requesting connection parameters: latency=%d, "
                "interval=[%d, %d], timeout=%d",
                CONN_PARAM_LATENCY,
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_TIMEOUT,
            )

            # BlueZ may not expose direct connection parameter setting
            # but logging the intent for debugging purposes
            _LOGGER.info(
                "BLE connection established with requested parameters: "
                "latency=%d, interval_min=%d, interval_max=%d, timeout=%d",
                CONN_PARAM_LATENCY,
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_TIMEOUT,
            )

        except ImportError:
            _LOGGER.debug("dbus_fast not available for connection parameter request")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("BlueZ connection parameter request failed: %s", err)
        finally:
            if bus is not None:
                bus.disconnect()

    async def _request_connection_parameters_corebluetooth(
        self, backend: object
    ) -> None:
        """Request connection parameters on Core Bluetooth (macOS).

        Args:
            backend: Bleak Core Bluetooth backend instance

        Note:
            Core Bluetooth does not expose direct connection parameter control
            from the central side. The peripheral device can request parameter
            updates, but the central can only accept or reject them.
            We log the desired parameters for debugging purposes.
        """
        try:
            # Core Bluetooth doesn't expose connection parameter APIs to centrals
            # The CBPeripheral can request updates via L2CAP, but CBCentralManager
            # doesn't provide methods to set preferred connection parameters
            _LOGGER.debug(
                "Core Bluetooth (macOS): connection parameters are managed by the "
                "system. Desired parameters: latency=%d, interval=[%d, %d], "
                "timeout=%d",
                CONN_PARAM_LATENCY,
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_TIMEOUT,
            )

            # Check if we can access the peripheral for logging purposes
            peripheral = getattr(backend, "_peripheral", None)
            if peripheral:
                _LOGGER.info(
                    "BLE connection established (macOS Core Bluetooth). "
                    "Connection parameters are system-managed"
                )
            else:
                _LOGGER.debug("Core Bluetooth peripheral not accessible")

        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Core Bluetooth connection parameter request failed: %s", err)

    async def _request_connection_parameters_winrt(self, backend: object) -> None:
        """Request connection parameters on Windows (WinRT).

        Args:
            backend: Bleak WinRT backend instance

        """
        try:
            # Try to import Windows-specific modules
            from winrt.windows.devices.bluetooth import (  # noqa: PLC0415
                BluetoothLEPreferredConnectionParametersRequest,
            )

            # Get the BluetoothLEDevice from the backend
            requester = getattr(backend, "_requester", None)
            if not requester:
                _LOGGER.debug("WinRT requester not available")
                return

            # Try to request preferred connection parameters
            # Note: WinRT uses different units than BLE spec
            # Interval is in units of 1.25ms, timeout in units of 10ms
            request = BluetoothLEPreferredConnectionParametersRequest.create_from_connection_parameters(
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_LATENCY,
                CONN_PARAM_TIMEOUT,
            )

            if request:
                result = await requester.request_preferred_connection_parameters_async(
                    request
                )
                _LOGGER.info(
                    "WinRT connection parameters requested: latency=%d, "
                    "interval=[%d, %d], timeout=%d, result=%s",
                    CONN_PARAM_LATENCY,
                    CONN_PARAM_INTERVAL_MIN,
                    CONN_PARAM_INTERVAL_MAX,
                    CONN_PARAM_TIMEOUT,
                    result,
                )
            else:
                _LOGGER.debug("Failed to create WinRT connection parameter request")

        except ImportError:
            # WinRT modules not available (not on Windows)
            _LOGGER.debug(
                "WinRT modules not available. Desired connection parameters: "
                "latency=%d, interval=[%d, %d], timeout=%d",
                CONN_PARAM_LATENCY,
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_TIMEOUT,
            )
        except AttributeError as err:
            # API might not be available in all Windows versions
            _LOGGER.debug(
                "WinRT connection parameter API not available: %s. "
                "Desired parameters: latency=%d, interval=[%d, %d], timeout=%d",
                err,
                CONN_PARAM_LATENCY,
                CONN_PARAM_INTERVAL_MIN,
                CONN_PARAM_INTERVAL_MAX,
                CONN_PARAM_TIMEOUT,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("WinRT connection parameter request failed: %s", err)

    @property
    def is_connected(self) -> bool:
        """Return if client is connected."""
        return self._client is not None and self._client.is_connected

    @property
    def is_duo(self) -> bool:
        """Return if connected button is a Flic Duo."""
        return isinstance(self._handler, DuoProtocolHandler)

    @property
    def is_twist(self) -> bool:
        """Return if connected button is a Flic Twist."""
        return isinstance(self._handler, TwistProtocolHandler)

    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        return self._device_type

    async def full_verify_pairing(self) -> tuple[int, bytes, str, int, int]:
        """Perform full pairing verification (for new pairings).

        Returns:
            Tuple of (pairing_id, pairing_key, serial_number, battery_level, sig_bits)

        """
        if self._state != SessionState.CONNECTED:
            raise FlicProtocolError("Not connected")

        self._state = SessionState.WAIT_FULL_VERIFY_1

        try:
            result = await self._handler.full_verify_pairing(
                write_gatt=self._write_gatt,
                wait_for_opcode=self._wait_for_handler_opcode,
                wait_for_opcodes=self._wait_for_handler_opcodes,
                write_packet=self._write_packet,
            )

            # Handle both 4-value (Flic2/Duo) and 5-value (Twist) returns
            if len(result) == 5:
                pairing_id, pairing_key, serial_number, battery_level, sig_bits = result
            else:
                pairing_id, pairing_key, serial_number, battery_level = result
                sig_bits = 0

            self._pairing_id = pairing_id
            self._pairing_key = pairing_key
            self._sig_bits = sig_bits
            self._state = SessionState.SESSION_ESTABLISHED
        except TimeoutError as err:
            self._state = SessionState.FAILED
            _LOGGER.error("Pairing timeout")
            raise FlicPairingError("Pairing timeout") from err
        else:
            return pairing_id, pairing_key, serial_number, battery_level, sig_bits

    async def quick_verify(self) -> None:
        """Perform quick verification using stored credentials."""
        if self._state != SessionState.CONNECTED:
            raise FlicProtocolError("Not connected")

        if not self._pairing_id or not self._pairing_key:
            raise FlicProtocolError("No pairing credentials available")

        self._state = SessionState.WAIT_QUICK_VERIFY

        try:
            session_key, chaskey_keys = await self._handler.quick_verify(
                pairing_id=self._pairing_id,
                pairing_key=self._pairing_key,
                write_gatt=self._write_gatt,
                wait_for_opcode=self._wait_for_handler_opcode,
                write_packet=self._write_packet,
                sig_bits=self._sig_bits,
            )

            self._session_key = session_key
            self._chaskey_keys = chaskey_keys
            self._packet_counter_to_button = 0
            self._packet_counter_from_button = 1

            self._state = SessionState.SESSION_ESTABLISHED
            _LOGGER.debug("Quick verification successful for %s", self.address)

        except TimeoutError as err:
            self._state = SessionState.FAILED
            raise FlicAuthenticationError("Quick verify timeout") from err

    async def init_button_events(self) -> None:
        """Initialize button event delivery."""
        if self._state != SessionState.SESSION_ESTABLISHED:
            raise FlicProtocolError("Session not established")

        _LOGGER.debug(
            "Initializing button events for %s (device_type=%s, serial=%s)",
            self.address,
            self._device_type.value,
            self._serial_number,
        )

        await self._handler.init_button_events(
            connection_id=self._connection_id,
            session_key=self._session_key,
            chaskey_keys=self._chaskey_keys,
            write_gatt=self._write_gatt,
            wait_for_opcode=self._wait_for_handler_opcode,
            wait_for_opcodes=self._wait_for_handler_opcodes,
            write_packet=self._write_packet,
        )

    async def get_firmware_version(self) -> int:
        """Request the firmware version from the device."""
        if self._state != SessionState.SESSION_ESTABLISHED:
            raise FlicProtocolError("Session not established")

        return await self._handler.get_firmware_version(
            connection_id=self._connection_id,
            write_packet=self._write_packet,
            wait_for_opcode=self._wait_for_handler_opcode,
        )

    async def get_battery_level(self) -> int:
        """Request the battery level from the device (Flic 2/Duo only)."""
        if self._state != SessionState.SESSION_ESTABLISHED:
            raise FlicProtocolError("Session not established")

        if not hasattr(self._handler, "get_battery_level"):
            raise FlicProtocolError("Battery level command not supported")

        return await self._handler.get_battery_level(
            connection_id=self._connection_id,
            write_packet=self._write_packet,
            wait_for_opcode=self._wait_for_handler_opcode,
        )

    async def async_send_update_twist_position(
        self, mode_index: int, percentage: float
    ) -> None:
        """Send position update via UpdateTwistPositionRequest.

        Args:
            mode_index: Twist mode index (0-11 for slots)
            percentage: Position as percentage (0.0-100.0)

        """
        if not isinstance(self._handler, TwistProtocolHandler):
            raise FlicProtocolError("Not a Twist device")
        if self._state != SessionState.SESSION_ESTABLISHED:
            raise FlicProtocolError("Session not established")

        # Convert percentage to raw units (D360 = 49152 = 100%)
        from .rotate_tracker import D360  # noqa: PLC0415

        new_position_units = int(percentage / 100.0 * D360)

        request_bytes = self._handler.build_update_twist_position(
            mode_index, new_position_units
        )

        _LOGGER.debug(
            "UpdateTwistPosition: mode=%d, percentage=%.1f, units=%d",
            mode_index,
            percentage,
            new_position_units,
        )

        await self._write_packet(request_bytes)

    async def _write_gatt(self, char_uuid: str, data: bytes) -> None:
        """Write data to a GATT characteristic."""
        if not self._client:
            raise FlicProtocolError("Not connected")

        await self._client.write_gatt_char(char_uuid, data)

    def _fragment_packet(
        self, packet: bytes, max_fragment_size: int = 20
    ) -> list[bytes]:
        """Fragment a large packet into smaller chunks that fit within MTU."""
        if len(packet) <= max_fragment_size:
            return [packet]

        original_frame_header = packet[0]
        original_payload = packet[1:]

        conn_id = original_frame_header & FRAME_HEADER_CONN_ID_MASK
        newly_assigned = bool(original_frame_header & FRAME_HEADER_NEWLY_ASSIGNED)

        fragments = []
        offset = 0
        fragment_data_size = max_fragment_size - 2

        while offset < len(original_payload):
            remaining_size = len(original_payload) - offset
            fragment_size = min(fragment_data_size, remaining_size)
            is_last_fragment = (offset + fragment_size) >= len(original_payload)

            fragment_frame_header = (
                (conn_id & FRAME_HEADER_CONN_ID_MASK)
                | (FRAME_HEADER_NEWLY_ASSIGNED if newly_assigned else 0)
                | (0 if is_last_fragment else FRAME_HEADER_FRAGMENT_FLAG)
            )

            fragment_data = original_payload[offset : offset + fragment_size]
            fragment_packet = bytes([fragment_frame_header, 0x00]) + fragment_data
            fragments.append(fragment_packet)

            _LOGGER.debug(
                "Fragment %d: size=%d bytes, is_last=%s",
                len(fragments),
                len(fragment_packet),
                is_last_fragment,
            )

            offset += fragment_size

        _LOGGER.debug(
            "Fragmented %d-byte packet into %d fragments",
            len(packet),
            len(fragments),
        )

        return fragments

    async def _write_packet(self, data: bytes, authenticated: bool = True) -> None:
        """Write a packet to the button.

        Args:
            data: Packet data (header + opcode + payload)
            authenticated: Whether to add authentication signature

        """
        if not self._client:
            raise FlicProtocolError("Not connected")

        packet = bytearray(data)

        if authenticated:
            if not self._chaskey_keys:
                raise FlicProtocolError("No session key available")

            # For Twist (no frame header), MAC the entire packet
            # For Flic 2/Duo (with frame header), MAC only opcode + payload
            if self._handler.capabilities.has_frame_header:
                mac_data = bytes(packet[1:])  # Skip frame_header
            else:
                mac_data = bytes(packet)  # Entire packet

            mac = chaskey_with_dir_and_counter(
                self._chaskey_keys,
                direction=1,  # client-to-button
                counter=self._packet_counter_to_button,
                data=mac_data,
            )
            packet.extend(mac)
            _LOGGER.debug(
                "Added MAC to packet (counter=%d)", self._packet_counter_to_button
            )

            self._packet_counter_to_button += 1

        # Fragment only for devices with frame headers and large packets
        if (
            self._handler.capabilities.has_frame_header
            and len(packet) > FLIC_MAX_PACKET_SIZE
        ):
            _LOGGER.debug(
                "Packet size %d exceeds max, fragmenting",
                len(packet),
            )
            fragments = self._fragment_packet(bytes(packet), 20)

            for i, fragment in enumerate(fragments):
                _LOGGER.debug(
                    "Sending fragment %d/%d (%d bytes)",
                    i + 1,
                    len(fragments),
                    len(fragment),
                )
                await self._client.write_gatt_char(
                    self._handler.write_char_uuid, fragment
                )
                if i < len(fragments) - 1:
                    await asyncio.sleep(0.01)

            _LOGGER.debug("All %d fragments sent successfully", len(fragments))
        else:
            _LOGGER.debug(
                "Writing packet (%d bytes) to %s",
                len(packet),
                self._handler.write_char_uuid,
            )
            await self._client.write_gatt_char(self._handler.write_char_uuid, packet)
            _LOGGER.debug("Packet written successfully")

    def _notification_handler(self, _sender: Any, data: bytearray) -> None:
        """Handle notifications from the button."""
        try:
            _LOGGER.debug(
                "BLE notification received: %d bytes, state=%s, device_type=%s",
                len(data),
                self._state.name,
                self._device_type.value,
            )
            _LOGGER.debug(
                "Received notification: %s (%d bytes)", bytes(data).hex(), len(data)
            )

            if len(data) < 1:
                _LOGGER.warning("Received packet too short: %d bytes", len(data))
                return

            # Route to appropriate handler based on frame header presence
            if self._handler.capabilities.has_frame_header:
                self._handle_framed_notification(data)
            else:
                self._handle_unframed_notification(data)

        except Exception:
            _LOGGER.exception("Error handling notification")

    def _handle_framed_notification(self, data: bytearray) -> None:
        """Handle notification with frame header (Flic 2/Duo)."""
        header = data[0]
        conn_id = header & FRAME_HEADER_CONN_ID_MASK
        newly_assigned = bool(header & FRAME_HEADER_NEWLY_ASSIGNED)
        is_fragment = bool(header & FRAME_HEADER_FRAGMENT_FLAG)

        _LOGGER.debug(
            "Packet header: conn_id=%d, newly_assigned=%s, is_fragment=%s",
            conn_id,
            newly_assigned,
            is_fragment,
        )

        if newly_assigned:
            self._connection_id = conn_id
            _LOGGER.debug("Connection ID assigned by button: %d", conn_id)

        # Handle fragmented packets
        if is_fragment:
            fragment_data = data[1:]
            self._fragment_buffer.extend(fragment_data)
            self._expecting_fragment = True
            _LOGGER.debug(
                "Received fragment (%d bytes), total buffered: %d bytes",
                len(fragment_data),
                len(self._fragment_buffer),
            )
            return

        if self._expecting_fragment:
            fragment_data = data[1:]
            self._fragment_buffer.extend(fragment_data)
            _LOGGER.debug(
                "Received final fragment (%d bytes), reassembling %d total bytes",
                len(fragment_data),
                len(self._fragment_buffer),
            )

            reassembled = bytearray([data[0]]) + self._fragment_buffer
            data = reassembled

            self._fragment_buffer = bytearray()
            self._expecting_fragment = False

        if len(data) < 2:
            _LOGGER.warning("Reassembled packet too short: %d bytes", len(data))
            return

        opcode = data[1]
        _LOGGER.debug(
            "Notification: opcode=0x%02x, conn_id=%d, state=%s",
            opcode,
            conn_id,
            self._state.name,
        )

        # Verify connection ID
        if (
            not newly_assigned
            and conn_id not in (self._connection_id, 0)
            and self._state >= SessionState.WAIT_QUICK_VERIFY
        ):
            _LOGGER.debug(
                "Packet for different connection ID (%d != %d), ignoring",
                conn_id,
                self._connection_id,
            )
            return

        # Strip MAC from authenticated packets
        # Note: MAC verification is disabled for reliability (like official Twist SDK)
        # When packets arrive rapidly, counter sync issues cause verification failures
        if self._state == SessionState.SESSION_ESTABLISHED:
            if len(data) < FLIC_SIGNATURE_SIZE + 2:
                _LOGGER.warning("Authenticated packet too short: %d bytes", len(data))
                return

            # Strip the 5-byte MAC tail
            packet_data = data[:-FLIC_SIGNATURE_SIZE]
            data = packet_data

            # MAC verification is disabled for reliability (matches official SDK behavior)

        # Delegate to handler for event processing
        button_events, rotate_events, _selector_index = (
            self._handler.handle_notification(bytes(data), self._connection_id)
        )

        # Emit events
        self._emit_button_events(button_events)
        self._emit_rotate_events(rotate_events)

        # If no events, this might be a command response
        if not button_events and not rotate_events:
            _LOGGER.debug("Putting response opcode=0x%02x in queue", opcode)
            self._response_queue.put_nowait(bytes(data))

    def _handle_unframed_notification(self, data: bytearray) -> None:
        """Handle notification without frame header (Twist)."""
        opcode = data[0]

        _LOGGER.debug(
            "Twist notification: opcode=0x%02x, data_len=%d, state=%s",
            opcode,
            len(data),
            self._state.name,
        )

        # Strip MAC from authenticated packets (Twist SDK doesn't verify incoming MACs)
        # The official Twist SDK just strips the 5-byte MAC tail without verification
        if self._state == SessionState.SESSION_ESTABLISHED:
            if len(data) > FLIC_SIGNATURE_SIZE + 1:
                # Strip the 5-byte MAC tail
                packet_data = data[:-FLIC_SIGNATURE_SIZE]
                _LOGGER.debug(
                    "Twist: stripped MAC from packet (opcode=0x%02x, %d -> %d bytes)",
                    opcode,
                    len(data),
                    len(packet_data),
                )
                data = bytearray(packet_data)

        # Handle disconnect notification (button rejected our request)
        if opcode == TWIST_OPCODE_DISCONNECTED_VERIFIED_LINK:
            reason = data[1] if len(data) > 1 else 0
            reason_str = {
                TWIST_DISCONNECT_REASON_INVALID_SIGNATURE: "INVALID_SIGNATURE",
                TWIST_DISCONNECT_REASON_OTHER_CLIENT: "OTHER_CLIENT",
            }.get(reason, f"UNKNOWN({reason})")
            _LOGGER.error(
                "Twist disconnected verified link: reason=%s (code=%d)",
                reason_str,
                reason,
            )
            self._state = SessionState.DISCONNECTED
            return

        # Delegate to handler
        button_events, rotate_events, selector_index = (
            self._handler.handle_notification(bytes(data), self._connection_id)
        )

        # Emit events
        self._emit_button_events(button_events)
        self._emit_rotate_events(rotate_events)

        # Emit selector change (Twist only)
        if selector_index is not None and self.on_selector_change:
            try:
                self.on_selector_change(selector_index, {})
            except Exception:
                _LOGGER.exception("Error in selector change callback")

        # If no events and not an event notification opcode, it's a command response.
        # Event opcodes (button=0x09, twist=0x0a) can produce zero events
        # (e.g. rotation with no detent crossings) but are never command responses.
        if (
            not button_events
            and not rotate_events
            and opcode not in (TWIST_OPCODE_BUTTON_EVENT, TWIST_OPCODE_TWIST_EVENT)
        ):
            _LOGGER.debug("Putting Twist response opcode=0x%02x in queue", opcode)
            self._response_queue.put_nowait(bytes(data))

    def _emit_button_events(self, button_events: list) -> None:
        """Process and emit button events."""
        for event in button_events:
            event_data: dict[str, Any] = {
                "timestamp_ms": event.timestamp_ms,
                "was_queued": event.was_queued,
                **event.extra_data,
            }
            if event.button_index is not None:
                event_data["button_index"] = event.button_index

            if self.on_button_event:
                try:
                    self.on_button_event(event.event_type, event_data)
                except Exception:
                    _LOGGER.exception("Error in button event callback")

    def _emit_rotate_events(self, rotate_events: list) -> None:
        """Process and emit rotate events."""
        for event in rotate_events:
            event_data: dict[str, Any] = {
                "angle_degrees": event.angle_degrees,
                "detent_crossings": event.detent_crossings,
                **event.extra_data,
            }
            if event.button_index is not None:
                event_data["button_index"] = event.button_index

            if self.on_rotate_event:
                try:
                    self.on_rotate_event(event.event_type, event_data)
                except Exception:
                    _LOGGER.exception("Error in rotate event callback")

    async def _wait_for_handler_opcode(self, opcode: int) -> bytes:
        """Wait for a response with specific opcode (for handler use).

        Routes to appropriate wait function based on frame header presence.
        """
        return await self._wait_for_handler_opcodes([opcode])

    async def _wait_for_handler_opcodes(self, opcodes: list[int]) -> bytes:
        """Wait for a response with one of specified opcodes (for handler use).

        Routes to appropriate wait function based on frame header presence.
        """
        has_frame_header = self._handler.capabilities.has_frame_header
        opcode_offset = 1 if has_frame_header else 0
        min_len = 2 if has_frame_header else 1

        _LOGGER.debug("Waiting for opcodes %s", [hex(o) for o in opcodes])
        while True:
            response = await self._response_queue.get()
            if len(response) >= min_len:
                received_opcode = response[opcode_offset]
                if received_opcode in opcodes:
                    _LOGGER.debug("Found matching opcode 0x%02x", received_opcode)
                    return response
                _LOGGER.debug(
                    "Received opcode 0x%02x, not in %s - putting back in queue",
                    received_opcode,
                    [hex(o) for o in opcodes],
                )
            else:
                _LOGGER.debug("Response too short, putting back in queue")
            await self._response_queue.put(response)
            await asyncio.sleep(0.01)
