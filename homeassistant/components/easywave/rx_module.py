"""Support for communicating with EASYWAVE RX11 transceivers.

This module implements the RxModule communication protocol used by
EASYWAVE RX11 devices, including packet encoding/decoding, version
queries, connection management, health checks, error tracking, and
callbacks for connection state changes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
import logging
import os
import struct
import threading
import time
from typing import Any

import serial
import serial.tools.list_ports

_LOGGER = logging.getLogger(__name__)

try:  # termios is not available on all platforms (e.g., Windows)
    import termios
except ImportError:  # pragma: no cover - platform specific
    termios = None  # type: ignore[assignment]

# Exception types raised by serial/termios operations.
# In Python 3.14 termios.error no longer inherits from OSError,
# so it must be caught explicitly when available.
_SERIAL_ERRORS: tuple[type[Exception], ...] = (serial.SerialException, OSError)
if termios is not None:
    _SERIAL_ERRORS = (*_SERIAL_ERRORS, termios.error)


# ====================================================================================================
# PROTOCOL CONSTANTS - SOP, EOP, Byte Stuffing
# ====================================================================================================

PREFIX = 0x80  # Prefix for byte stuffing
SOP = 0x81  # Start-of-packet
EOP = 0x82  # End-of-packet

STUFFING_MIN = 0x80  # Start of range which is stuffed
STUFFING_MAX = 0x82  # End of range which is stuffed
STUFFING_ADDEND = 0xFF & (-0x80)  # Addend to get the replacement (0x80)


# ====================================================================================================
# FUNCTION CODES
# ====================================================================================================


class FunctionCode(IntEnum):
    """Function codes for Core integration."""

    # Easywave button receive (for future monitoring)
    EW_RCV_BUTTON = 0x01
    # Easywave send command (for future control)
    EW_SEND_CMD = 0x02
    # Hardware/firmware version queries
    MA_QUERY_HW_VER = 0xC0
    MA_QUERY_FW_VER = 0xC1
    # Cancel operations
    CANCEL_IO = 0xFE
    CANCEL_ALL_IO = 0xFF
    # Ping (for health checks)
    PING_RCV = 0xF0


# Continuous receive function codes
CONTINUOUS_RCV_FUNCTIONS: frozenset[int] = frozenset(
    {
        FunctionCode.EW_RCV_BUTTON,
    }
)


# ====================================================================================================
# ERROR CODES
# ====================================================================================================


class ErrorCode(IntEnum):
    """Error codes returned by operations."""

    SUCCESS = 0x00
    ERR_CANCELED = 0x01
    ERR_OUT_OF_QUEUE = 0x02
    ERR_INVALID_REQUEST = 0x03
    ERR_SIZE_MISMATCH = 0x04
    ERR_INVALID_PARAMETER = 0x05
    ERR_INCOMPLETE_FW = 0x06
    ERR_RF_TIMEOUT = 0x07
    ERR_INVALID_SERIAL = 0x08
    ERR_SUPERSEDED = 0x09
    ERR_INCOMPAT_FW = 0x0A
    ERR_SERIAL_FILTER = 0x0B
    ERR_FILTER_OUT_OF_MEM = 0x0C
    ERR_INVALID_SEC_REPLY = 0x0D
    ERR_TOO_LATE = 0x0E
    ERR_FAILSTATE = 0xFF


# ====================================================================================================
# REQUEST & COMPLETION STRUCTURES
# ====================================================================================================


@dataclass
class IRP:
    """I/O Request Packet - represents a command to be sent."""

    function: int
    params: bytes = field(default_factory=bytes)


@dataclass
class ICP:
    """I/O Completion Packet - represents a response received."""

    handle: int = 0
    result: int = ErrorCode.ERR_FAILSTATE
    data: bytes = field(default_factory=bytes)


@dataclass
class Request:
    """Represents a pending request with its IRP and expected ICP."""

    irp: IRP
    irp_byte_count: int
    expected_icp_byte_count: int
    req_str: str

    # State tracking
    completed: bool = False
    queued: bool = False
    cancel: bool = False
    handle: int = 0
    is_continuous: bool = False
    error: str | None = None
    done: bool = False

    # Result
    icp: ICP = field(default_factory=ICP)

    # Synchronization
    event: threading.Event = field(default_factory=threading.Event)
    future: asyncio.Future | None = None

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for request completion."""
        return self.event.wait(timeout)

    def signal(self):
        """Signal request completion."""
        self.completed = True
        self.event.set()


# ====================================================================================================
# BYTE STUFFING FUNCTIONS
# ====================================================================================================


def apply_byte_stuffing(data: bytes) -> bytes:
    """Apply byte stuffing to data bytes."""
    result = bytearray()
    for byte in data:
        if STUFFING_MIN <= byte <= STUFFING_MAX:
            result.append(PREFIX)
            result.append((byte + STUFFING_ADDEND) & 0xFF)
        else:
            result.append(byte)
    return bytes(result)


def remove_byte_stuffing(data: bytes) -> tuple[bytes, bool]:
    """Remove byte stuffing from data."""
    result = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == PREFIX:
            if i + 1 >= len(data):
                return bytes(result), False
            next_byte = data[i + 1]
            if (
                ((STUFFING_MIN + STUFFING_ADDEND) & 0xFF)
                <= next_byte
                <= ((STUFFING_MAX + STUFFING_ADDEND) & 0xFF)
            ):
                result.append((next_byte + STUFFING_ADDEND) & 0xFF)
                i += 2
            else:
                return bytes(result), False
        else:
            result.append(byte)
            i += 1
    return bytes(result), True


# ====================================================================================================
# PACKET ENCODING/DECODING
# ====================================================================================================


def encode_irp(irp: IRP) -> bytes:
    """Encode an IRP into a byte packet with SOP, function, params, stuffing, and EOP."""
    buffer = bytearray([irp.function])
    buffer.extend(irp.params)
    stuffed = apply_byte_stuffing(bytes(buffer))
    packet = bytearray([SOP])
    packet.extend(stuffed)
    packet.append(EOP)
    return bytes(packet)


def decode_packet(raw_buffer: bytes) -> tuple[ICP | None, int, bool]:
    """Decode a received packet into an ICP.

    Note: raw_buffer is already unstuffed by _process_received_byte()!
    It still contains SOP and EOP markers but byte stuffing has been removed.

    Returns:
        (icp, function_code, success)
    """
    # Remove SOP and EOP
    if len(raw_buffer) < 2 or raw_buffer[0] != SOP or raw_buffer[-1] != EOP:
        return None, 0, False

    # Payload is already unstuffed - no need to call remove_byte_stuffing()!
    payload = raw_buffer[1:-1]

    if len(payload) < 2:
        return None, 0, False

    # Parse handle (first 2 bytes)
    handle = (payload[0] << 8) | payload[1]

    # Check if this is just an IPP (handle only) or a full ICP
    if len(payload) == 2:
        # IPP - just a handle
        icp = ICP(handle=handle, result=ErrorCode.SUCCESS, data=b"")
        return icp, 0, True

    # Full ICP - handle + result + data
    result = payload[2]
    data = payload[3:] if len(payload) > 3 else b""

    icp = ICP(handle=handle, result=result, data=data)
    return icp, 0, True


# ====================================================================================================
# IRP PARAMETER ENCODING
# ====================================================================================================


def encode_uint16(value: int) -> bytes:
    """Encode a uint16 as big-endian bytes."""
    return struct.pack(">H", value)


def encode_uint32(value: int) -> bytes:
    """Encode a uint32 as big-endian bytes."""
    return struct.pack(">I", value)


def encode_serial_array(serial_bytes: bytes) -> bytes:
    """Encode a 16-byte serial number."""
    if len(serial_bytes) != 16:
        raise ValueError(f"Serial must be 16 bytes, got {len(serial_bytes)}")
    return serial_bytes


# ====================================================================================================
# ICP DATA PARSING
# ====================================================================================================


def parse_icp_data(icp: ICP, function: int) -> dict[str, Any]:
    """Parse ICP data based on the function code."""
    data = icp.data
    result: dict[str, Any] = {}

    if icp.result != ErrorCode.SUCCESS:
        return result

    offset = 0

    try:
        if function == FunctionCode.EW_RCV_BUTTON:
            result["info_type"] = data[offset]
            offset += 1
            result["transmitter"] = data[offset : offset + 16]
            offset += 16
            result["info_data"] = (
                data[offset : offset + 1] if offset < len(data) else bytes(1)
            )

        elif function == FunctionCode.MA_QUERY_HW_VER:
            result["hw_version_str"] = data[offset : offset + 16]

        elif function == FunctionCode.MA_QUERY_FW_VER:
            result["major_version"] = data[offset]
            offset += 1
            result["minor_version"] = data[offset]
            offset += 1
            result["incomplete_fw"] = data[offset] != 0 if offset < len(data) else False

    except (IndexError, struct.error) as e:
        _LOGGER.error("Error parsing ICP data for function 0x%02x: %s", function, e)

    return result


# ====================================================================================================
# MAIN RX MODULE CLASS
# ====================================================================================================


class RxModule:
    """Pure Python implementation of EASYWAVE RX11 RxModule - Core Version.

    This is a minimal but complete implementation focused on:
    - Hardware/firmware version queries
    - Button telegram receiving
    - Health monitoring
    - Graceful disconnect
    - COM port compatibility (no direct USB calls)
    """

    MAX_REQUEST_COUNT = 8
    MAX_REQUEST_QUEUED = 12

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        """Initialize the RxModule."""
        self.port = port
        self.baudrate = baudrate

        # Serial connection
        self._serial: serial.Serial | None = None
        self._connected = False
        self._shutdown_requested = False
        self._is_reconnecting = False

        # Request queues
        self._tx_req_queued: list[Request | None] = [None] * self.MAX_REQUEST_QUEUED
        self._tx_req_queued_front = -1
        self._tx_req_queued_rear = -1
        self._tx_req_queued_size = 0

        self._tx_req_sent: list[Request | None] = [None] * self.MAX_REQUEST_COUNT
        self._tx_req_sent_front = -1
        self._tx_req_sent_rear = -1
        self._tx_req_sent_size = 0

        self._req_pending: dict[int, Request] = {}

        # State tracking
        self._state_good = True
        self._connection_healthy = True
        self._hardware_error = False
        self._last_error: str | None = None
        self._last_successful_communication = time.time()
        self._reconnect_attempts = 0
        self._reconnect_delay_base = 1.0
        self._health_check_interval = 30.0

        # Startup tolerance - ignore decode errors on initial connection
        self._startup_tolerance_until: float = 0.0
        self._startup_tolerance_duration: float = 5.0
        self._reconnect_startup_tolerance_duration: float = 10.0

        # Cancel tolerance - allow unknown handle ICPs after cancel_all_io
        self._cancel_tolerance_until: float = 0.0

        # RX state
        self._rx_sop = False
        self._rx_raw_buffer = bytearray()
        self._rx_stuffing = False

        # Threading
        self._protocol_lock = threading.RLock()
        self._file_lock = threading.Lock()
        self._serial_handler_thread: threading.Thread | None = None

        # Callbacks
        self._disconnect_callback: Callable[[], None] | None = None

    # ================================================================================================
    # PROPERTIES
    # ================================================================================================

    def set_disconnect_callback(self, callback: Callable[[], None] | None) -> None:
        """Set a callback to be called when a disconnect/hardware error occurs."""
        self._disconnect_callback = callback

    def _notify_disconnect(self) -> None:
        """Notify the disconnect callback if registered."""
        if self._disconnect_callback is not None:
            try:
                self._disconnect_callback()
            except (OSError, RuntimeError) as e:
                _LOGGER.warning("Error calling disconnect callback: %s", e)

    @property
    def is_connected(self) -> bool:
        """Check if module is connected and healthy."""
        with self._protocol_lock:
            return self._connected and self._connection_healthy and self._state_good

    @property
    def state_good(self) -> bool:
        """Check if module state is good (no protocol errors)."""
        with self._protocol_lock:
            return self._state_good

    @property
    def connection_status(self) -> str:
        """Get detailed connection status."""
        with self._protocol_lock:
            if not self._connected:
                return "disconnected"
            if self._hardware_error:
                return "hardware_error"
            if not self._connection_healthy:
                return "reconnecting"
            if not self._state_good:
                return "error"
            return "connected"

    @property
    def has_hardware_error(self) -> bool:
        """Check if a hardware error occurred (USB disconnected, I/O error, etc.)."""
        with self._protocol_lock:
            return self._hardware_error

    @property
    def last_error(self) -> str | None:
        """Get the last error message."""
        with self._protocol_lock:
            return self._last_error

    # ================================================================================================
    # CONNECTION MANAGEMENT
    # ================================================================================================

    def connect(self) -> bool:
        """Connect to the RX11 module."""
        try:
            self._shutdown_requested = False

            # Open serial connection
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.001,
                write_timeout=1.0,
            )

            # Reset state
            self._reset_queues()
            self.cancel_all_io_requests()
            self._reset_rx_state()

            # Aggressive buffer clearing
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

            drain_end = time.time() + 0.4
            drained = 0
            while time.time() < drain_end:
                try:
                    waiting = self._serial.in_waiting
                    if waiting > 0:
                        self._serial.read(waiting)
                        drained += waiting
                    else:
                        time.sleep(0.02)
                except _SERIAL_ERRORS:
                    break

            if drained > 0:
                _LOGGER.debug("Drained %d stale bytes from serial buffer", drained)

            self._serial.reset_input_buffer()

            # Set startup tolerance
            tolerance_duration = (
                self._reconnect_startup_tolerance_duration
                if self._is_reconnecting
                else self._startup_tolerance_duration
            )
            self._startup_tolerance_until = time.time() + tolerance_duration

            # Reset health state
            with self._protocol_lock:
                self._state_good = True
                self._connection_healthy = True
                self._hardware_error = False
                self._last_error = None
                self._last_successful_communication = time.time()
                self._reconnect_attempts = 0

            # Start serial handler thread
            self._serial_handler_thread = threading.Thread(
                target=self._serial_handler, daemon=True, name="RxModule-SerialHandler"
            )
            self._serial_handler_thread.start()

            self._connected = True
        except _SERIAL_ERRORS:
            return False
        else:
            return True

    def flush_serial_buffer(self):
        """Flush serial input buffer and reset RX state.

        Call this before sending critical commands (e.g. version queries)
        to drain any stale data that survived the initial connect drain.
        Safe to call while the serial handler thread is running.
        """
        if not self._serial or not self._serial.is_open:
            return
        try:
            self._serial.reset_input_buffer()
            drain_end = time.time() + 0.15
            drained = 0
            while time.time() < drain_end:
                waiting = self._serial.in_waiting
                if waiting > 0:
                    self._serial.read(waiting)
                    drained += waiting
                else:
                    time.sleep(0.01)
            if drained > 0:
                _LOGGER.debug("Flushed %d stale bytes from serial buffer", drained)
        except _SERIAL_ERRORS:
            pass

    def dispose(self):
        """Disconnect and cleanup."""
        self._shutdown_requested = True
        self.cancel_all_io_requests()

        # Wait for serial handler thread
        if self._serial_handler_thread and self._serial_handler_thread.is_alive():
            self._serial_handler_thread.join(timeout=3.0)

        # Drain remaining bytes
        if self._serial and self._serial.is_open:
            try:
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()
                drain_end = time.time() + 0.2
                while time.time() < drain_end:
                    if self._serial.in_waiting > 0:
                        self._serial.read(self._serial.in_waiting)
                    else:
                        time.sleep(0.02)
            except _SERIAL_ERRORS:
                pass

        if self._serial:
            try:
                self._serial.close()
            except _SERIAL_ERRORS as e:
                _LOGGER.debug("Error closing serial connection: %s", e)
            finally:
                self._serial = None

        self._connected = False

    def _reset_queues(self):
        """Reset all request queues."""
        self._tx_req_queued = [None] * self.MAX_REQUEST_QUEUED
        self._tx_req_queued_front = -1
        self._tx_req_queued_rear = -1
        self._tx_req_queued_size = 0

        self._tx_req_sent = [None] * self.MAX_REQUEST_COUNT
        self._tx_req_sent_front = -1
        self._tx_req_sent_rear = -1
        self._tx_req_sent_size = 0

        self._req_pending.clear()

    def _reset_rx_state(self):
        """Reset RX state machine."""
        self._rx_sop = False
        self._rx_raw_buffer = bytearray()
        self._rx_stuffing = False

    # ================================================================================================
    # REQUEST MANAGEMENT
    # ================================================================================================

    def _create_request(
        self, irp: IRP, irp_byte_count: int, expected_icp_byte_count: int, req_str: str
    ) -> Request:
        """Create a new request."""
        return Request(
            irp=irp,
            irp_byte_count=irp_byte_count,
            expected_icp_byte_count=expected_icp_byte_count,
            req_str=req_str,
            is_continuous=irp.function in CONTINUOUS_RCV_FUNCTIONS,
        )

    def _place_request(self, req: Request):
        """Place a request in the queue or send it immediately."""
        with self._protocol_lock:
            if not self._state_good:
                req.icp = ICP(handle=0, result=ErrorCode.ERR_FAILSTATE)
                req.signal()
                return

            if (
                self._tx_req_queued_size == 0
                and (self._tx_req_sent_size + len(self._req_pending))
                < self.MAX_REQUEST_COUNT
            ):
                self._enqueue_sent(req)
                self._write_to_buffer(req.irp, req.req_str)
            elif self._tx_req_queued_size < self.MAX_REQUEST_QUEUED:
                self._remove_canceled_queued_requests()
                self._enqueue_queued(req)
                req.queued = True
            else:
                req.icp = ICP(handle=0, result=ErrorCode.ERR_OUT_OF_QUEUE)
                req.signal()

    def _enqueue_queued(self, req: Request):
        """Add request to queued list."""
        if self._tx_req_queued_front == -1:
            self._tx_req_queued_front = 0
        self._tx_req_queued_rear = (
            self._tx_req_queued_rear + 1
        ) % self.MAX_REQUEST_QUEUED
        self._tx_req_queued[self._tx_req_queued_rear] = req
        self._tx_req_queued_size += 1

    def _dequeue_queued(self) -> Request | None:
        """Remove request from queued list."""
        if self._tx_req_queued_size == 0:
            return None
        req = self._tx_req_queued[self._tx_req_queued_front]
        self._tx_req_queued[self._tx_req_queued_front] = None
        self._tx_req_queued_front = (
            self._tx_req_queued_front + 1
        ) % self.MAX_REQUEST_QUEUED
        self._tx_req_queued_size -= 1
        return req

    def _enqueue_sent(self, req: Request):
        """Add request to sent list."""
        if self._tx_req_sent_front == -1:
            self._tx_req_sent_front = 0
        self._tx_req_sent_rear = (self._tx_req_sent_rear + 1) % self.MAX_REQUEST_COUNT
        self._tx_req_sent[self._tx_req_sent_rear] = req
        self._tx_req_sent_size += 1

    def _dequeue_sent(self) -> Request | None:
        """Remove request from sent list."""
        if self._tx_req_sent_size == 0:
            return None
        req = self._tx_req_sent[self._tx_req_sent_front]
        self._tx_req_sent[self._tx_req_sent_front] = None
        self._tx_req_sent_front = (self._tx_req_sent_front + 1) % self.MAX_REQUEST_COUNT
        self._tx_req_sent_size -= 1
        return req

    def _remove_canceled_queued_requests(self):
        """Remove canceled requests from the queued list."""
        while (
            self._tx_req_queued_size > 0
            and self._tx_req_queued[self._tx_req_queued_front]
            and self._tx_req_queued[self._tx_req_queued_front].cancel
        ):
            self._dequeue_queued()

    # ================================================================================================
    # SERIAL COMMUNICATION
    # ================================================================================================

    def _write_to_buffer(self, irp: IRP, req_str: str):
        """Write an IRP to the serial connection."""
        if not self._serial or self._shutdown_requested:
            return

        try:
            if not self._is_serial_port_valid():
                _LOGGER.error("Serial port no longer valid (USB disconnected?)")
                with self._protocol_lock:
                    self._state_good = False
                    self._connection_healthy = False
                    self._connected = False
                    self._hardware_error = True
                    self._notify_disconnect()
                return

            packet = encode_irp(irp)

            with self._file_lock:
                if self._serial and not self._shutdown_requested:
                    bytes_written = self._serial.write(packet)

                    if bytes_written != len(packet):
                        _LOGGER.error(
                            "Serial write incomplete: %d of %d written",
                            bytes_written,
                            len(packet),
                        )
                        with self._protocol_lock:
                            self._state_good = False
                            self._connection_healthy = False
                        return

        except _SERIAL_ERRORS as e:
            if not self._shutdown_requested:
                _LOGGER.error("Serial error during write: %s", e)
                with self._protocol_lock:
                    self._state_good = False
                    self._connection_healthy = False
                    self._hardware_error = True

    def _is_serial_port_valid(self) -> bool:
        """Check if the serial port is still valid."""
        try:
            if not self._serial or not self._serial.is_open:
                return False

            if hasattr(self._serial, "port") and self._serial.port:
                port = self._serial.port
                if os.name == "nt":
                    available = (p.device for p in serial.tools.list_ports.comports())
                    if port.upper() not in (p.upper() for p in available):
                        _LOGGER.warning("Serial port %s no longer exists", port)
                        return False
                elif os.path.isabs(port) and not os.path.exists(port):
                    _LOGGER.warning("Serial port %s no longer exists", port)
                    return False
        except (OSError, ValueError) as e:
            _LOGGER.warning("Error checking serial port validity: %s", e)
            return False
        else:
            return True

    def _serial_handler(self):
        """Main serial handler thread."""
        last_health_check = time.time()

        while not self._shutdown_requested:
            try:
                # Health check periodically
                if time.time() - last_health_check > self._health_check_interval:
                    self._check_connection_health()
                    last_health_check = time.time()

                if not self._is_serial_port_valid():
                    if not self._shutdown_requested:
                        _LOGGER.error(
                            "Serial port invalid - USB device may have been removed"
                        )
                        with self._protocol_lock:
                            self._state_good = False
                            self._connection_healthy = False
                            self._hardware_error = True
                            self._connected = False
                        self._notify_disconnect()
                    break

                # Read available bytes
                try:
                    while self._serial and self._serial.in_waiting > 0:
                        byte_data = self._serial.read(1)
                        if not byte_data:
                            break
                        byte = byte_data[0]
                        self._process_received_byte(byte)
                except _SERIAL_ERRORS:
                    if not self._shutdown_requested:
                        with self._protocol_lock:
                            self._state_good = False
                            self._connection_healthy = False
                            self._hardware_error = True
                            self._connected = False
                        self._notify_disconnect()
                    break

                self._process_queued_requests()
                time.sleep(0.01)

            except _SERIAL_ERRORS as e:
                if not self._shutdown_requested:
                    _LOGGER.warning("Serial handler error: %s", e)
                    with self._protocol_lock:
                        self._state_good = False
                        self._connection_healthy = False
                        self._hardware_error = True
                        self._connected = False
                    self._notify_disconnect()
                break

    def _process_received_byte(self, byte: int):
        """Process a single received byte."""
        if not self._state_good:
            return

        # Handle start-of-packet before buffering to avoid accumulating
        # stray bytes when not synchronized.
        if byte == SOP:
            if self._rx_sop:
                _LOGGER.warning(
                    "Unexpected SOP while already in packet (len=%d)",
                    len(self._rx_raw_buffer),
                )
            # Always resynchronize buffer on SOP to discard any stray bytes
            self._rx_raw_buffer = bytearray([SOP])
            self._rx_sop = True
            self._rx_stuffing = False
            return

        # If we have not yet seen SOP, ignore bytes and ensure the buffer
        # does not grow without bound.
        if not self._rx_sop:
            self._rx_raw_buffer = bytearray()
            return

        # From here on, we are inside a packet: buffer the byte.
        self._rx_raw_buffer.append(byte)

        if byte == EOP:
            if self._rx_stuffing:
                _LOGGER.warning("Unexpected EOP while waiting for stuffed byte")
                self._reset_rx_state()
                return

            self._process_complete_packet()
            return

        if not self._rx_stuffing and byte == PREFIX:
            self._rx_stuffing = True
            self._rx_raw_buffer.pop()
            return

        if self._rx_stuffing:
            if (
                ((STUFFING_MIN + STUFFING_ADDEND) & 0xFF)
                <= byte
                <= ((STUFFING_MAX + STUFFING_ADDEND) & 0xFF)
            ):
                unstuffed = (byte + STUFFING_ADDEND) & 0xFF
                self._rx_raw_buffer[-1] = unstuffed
                self._rx_stuffing = False
            else:
                _LOGGER.warning("Invalid stuffed byte 0x%02x", byte)
                self._rx_raw_buffer = bytearray()
                self._rx_sop = False
                self._rx_stuffing = False
                return

        if len(self._rx_raw_buffer) >= 128:
            _LOGGER.warning("Packet too large (>128 bytes)")
            self._reset_rx_state()

    def _process_complete_packet(self):
        """Process a complete received packet."""
        raw_buffer = bytes(self._rx_raw_buffer)
        self._rx_raw_buffer = bytearray()
        self._rx_sop = False

        icp, _, success = decode_packet(raw_buffer)
        if not success:
            in_startup = time.time() < self._startup_tolerance_until
            if in_startup:
                _LOGGER.debug(
                    "Discarding invalid packet during startup (len=%d)", len(raw_buffer)
                )
            elif len(raw_buffer) > 0:
                _LOGGER.warning(
                    "Failed to decode packet (len=%d, hex=%s)",
                    len(raw_buffer),
                    raw_buffer.hex()[:80],
                )

            # If we have sent requests waiting and we're outside startup,
            # fail the oldest to recover sync
            if not in_startup:
                with self._protocol_lock:
                    if self._tx_req_sent_size > 0 and len(self._req_pending) == 0:
                        _LOGGER.error(
                            "Corrupt packet with pending requests — failing oldest sent request to recover sync"
                        )
                        req = self._dequeue_sent()
                        if req:
                            req.icp = ICP(handle=0, result=ErrorCode.ERR_FAILSTATE)
                            req.signal()
            return

        self._mark_communication_success()

        icp_byte_count = len(raw_buffer) - 2
        handle = icp.handle

        if icp_byte_count == 2:
            self._process_ipp(handle, raw_buffer)
        else:
            self._process_icp(handle, icp, icp_byte_count, raw_buffer)

    def _process_ipp(self, handle: int, raw_buffer: bytes):
        """Process an I/O Pending Packet."""
        in_startup = time.time() < self._startup_tolerance_until

        with self._protocol_lock:
            if self._tx_req_sent_size == 0:
                if in_startup:
                    _LOGGER.debug("Ignoring unexpected IPP during startup")
                    return
                _LOGGER.warning(
                    "Unexpected IPP (handle=0x%04x) - no request pending", handle
                )
                return

            req = self._dequeue_sent()
            if not req:
                return

            if handle == 0:
                _LOGGER.warning("Received zero handle - failing request")
                req.icp = ICP(handle=0, result=ErrorCode.ERR_INVALID_REQUEST)
                req.signal()
                return

            if handle in self._req_pending:
                _LOGGER.warning("Duplicate handle 0x%04x", handle)
                old_req = self._req_pending.pop(handle)
                old_req.icp = ICP(handle=0, result=ErrorCode.ERR_INVALID_REQUEST)
                old_req.signal()
                req.icp = ICP(handle=0, result=ErrorCode.ERR_INVALID_REQUEST)
                req.signal()
                return

            req.handle = handle
            self._req_pending[handle] = req

            if req.cancel:
                self._cancel_request_impl(req)

    def _process_icp(
        self, handle: int, icp: ICP, icp_byte_count: int, raw_buffer: bytes
    ):
        """Process an I/O Completion Packet."""
        in_startup = time.time() < self._startup_tolerance_until

        with self._protocol_lock:
            req: Request | None = None

            if handle != 0:
                req = self._req_pending.pop(handle, None)
                if not req:
                    if time.time() < self._cancel_tolerance_until or in_startup:
                        _LOGGER.debug(
                            "ICP for unknown handle 0x%04x during tolerance period",
                            handle,
                        )
                        return
                    _LOGGER.warning("ICP for unknown handle 0x%04x - ignoring", handle)
                    return
            else:
                req = self._dequeue_sent()
                if not req:
                    if in_startup:
                        _LOGGER.debug("Ignoring synchronous ICP during startup")
                        return
                    _LOGGER.warning("Unexpected synchronous ICP - no request pending")
                    return

            # Validate ICP length
            if icp.result == ErrorCode.SUCCESS:
                if icp_byte_count != req.expected_icp_byte_count:
                    if in_startup:
                        _LOGGER.debug(
                            "ICP length mismatch for '%s' during startup: got %d, expected %d "
                            "— discarding stale ICP, keeping request alive",
                            req.req_str,
                            icp_byte_count,
                            req.expected_icp_byte_count,
                        )
                        if handle != 0:
                            self._req_pending[handle] = req
                        return
                    _LOGGER.warning(
                        "ICP length mismatch for '%s': got %d, expected %d — failing request",
                        req.req_str,
                        icp_byte_count,
                        req.expected_icp_byte_count,
                    )
                    req.icp = ICP(handle=handle, result=ErrorCode.ERR_SIZE_MISMATCH)
                    req.signal()
                    return
            elif icp_byte_count != 3:
                _LOGGER.warning(
                    "Error ICP has unexpected length %d (expected 3) for '%s'",
                    icp_byte_count,
                    req.req_str,
                )
                req.icp = ICP(handle=handle, result=ErrorCode.ERR_SIZE_MISMATCH)
                req.signal()
                return

            if icp.result == ErrorCode.ERR_OUT_OF_QUEUE:
                if self._tx_req_queued_size < self.MAX_REQUEST_QUEUED:
                    self._enqueue_queued(req)
                    return
                _LOGGER.warning("Cannot requeue - queue full")
                req.icp = ICP(handle=handle, result=ErrorCode.ERR_OUT_OF_QUEUE)
                req.signal()
                return

            req.icp = icp
            req.signal()

    def _process_queued_requests(self):
        """Process queued requests and send if possible."""
        with self._protocol_lock:
            self._remove_canceled_queued_requests()

            while (
                self._tx_req_queued_size > 0
                and (self._tx_req_sent_size + len(self._req_pending))
                < self.MAX_REQUEST_COUNT
            ):
                req = self._dequeue_queued()
                if not req:
                    break

                state_good = self._state_good

                if not state_good:
                    req.icp = ICP(handle=0, result=ErrorCode.ERR_FAILSTATE)
                    req.signal()
                else:
                    req.queued = False
                    self._enqueue_sent(req)
                    self._write_to_buffer(req.irp, req.req_str)

    def _check_connection_health(self):
        """Check if connection is healthy."""
        with self._protocol_lock:
            if not self._connection_healthy:
                return

            time_since_comm = time.time() - self._last_successful_communication
            irps_waiting = self._tx_req_sent_size
            non_continuous_pending = sum(
                1 for req in self._req_pending.values() if not req.is_continuous
            )

            if time_since_comm > self._health_check_interval and (
                irps_waiting > 0 or non_continuous_pending > 0
            ):
                _LOGGER.error(
                    "RX11 Connection UNHEALTHY - no response for %.1fs! "
                    "(IRPs without IPP=%d, Commands without ICP=%d)",
                    time_since_comm,
                    irps_waiting,
                    non_continuous_pending,
                )
                self._state_good = False

    def _mark_communication_success(self):
        """Mark that we had a successful communication."""
        with self._protocol_lock:
            self._last_successful_communication = time.time()
            self._reconnect_attempts = 0

    # ================================================================================================
    # CANCEL OPERATIONS
    # ================================================================================================

    def _cancel_request_impl(self, req: Request):
        """Send a cancel IRP for a specific request."""
        cancel_params = encode_uint16(req.handle)
        cancel_irp = IRP(function=FunctionCode.CANCEL_IO, params=cancel_params)
        self._write_to_buffer(cancel_irp, "CANCEL_IO")

    def cancel_all_io_requests(self):
        """Cancel all pending requests."""
        with self._protocol_lock:
            while self._tx_req_queued_size > 0:
                req = self._dequeue_queued()
                if req and not req.cancel:
                    req.icp = ICP(handle=0, result=ErrorCode.ERR_CANCELED)
                    req.signal()

            while self._tx_req_sent_size > 0:
                req = self._dequeue_sent()
                if req and not req.cancel:
                    req.icp = ICP(handle=0, result=ErrorCode.ERR_CANCELED)
                    req.signal()

            cancel_irp = IRP(function=FunctionCode.CANCEL_ALL_IO, params=b"")
            self._write_to_buffer(cancel_irp, "CANCEL_ALL_IO")

            for _handle, req in list(self._req_pending.items()):
                if not req.cancel:
                    req.icp = ICP(handle=0, result=ErrorCode.ERR_CANCELED)
                    req.signal()
            self._req_pending.clear()

            self._cancel_tolerance_until = time.time() + 2.0

    # ================================================================================================
    # HIGH-LEVEL API FUNCTIONS
    # ================================================================================================

    def query_hw_version(self, timeout: float = 5.0) -> tuple[int, bytes]:
        """Query hardware version."""
        irp = IRP(function=FunctionCode.MA_QUERY_HW_VER, params=b"")
        req = self._create_request(irp, 1, 19, "MA_QUERY_HW_VER")

        self._place_request(req)
        if not req.wait(timeout):
            self.cancel_all_io_requests()
            return ErrorCode.ERR_RF_TIMEOUT, bytes(16)

        if req.icp.result == ErrorCode.SUCCESS:
            parsed = parse_icp_data(req.icp, FunctionCode.MA_QUERY_HW_VER)
            hw_str = parsed.get("hw_version_str", bytes(16))
            return req.icp.result, hw_str
        return req.icp.result, bytes(16)

    def query_fw_version(self, timeout: float = 5.0) -> tuple[int, int, int, bool]:
        """Query firmware version."""
        irp = IRP(function=FunctionCode.MA_QUERY_FW_VER, params=b"")
        req = self._create_request(irp, 1, 6, "MA_QUERY_FW_VER")

        self._place_request(req)
        if not req.wait(timeout):
            self.cancel_all_io_requests()
            return ErrorCode.ERR_RF_TIMEOUT, 0, 0, False

        if req.icp.result == ErrorCode.SUCCESS:
            parsed = parse_icp_data(req.icp, FunctionCode.MA_QUERY_FW_VER)
            major = parsed.get("major_version", 0)
            minor = parsed.get("minor_version", 0)
            incomplete = parsed.get("incomplete_fw", False)
            return req.icp.result, major, minor, incomplete
        return req.icp.result, 0, 0, False

    def ping(self, duration: int = 5) -> int:
        """Ping the module."""
        irp = IRP(function=FunctionCode.PING_RCV, params=b"")
        req = self._create_request(irp, 1, 3, "PING_RCV")

        self._place_request(req)
        if not req.wait(duration):
            return ErrorCode.ERR_RF_TIMEOUT

        return req.icp.result
