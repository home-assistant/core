"""Flic 2/Duo message protocol dataclasses.

This module implements the Flic protocol message types following the SDK pattern,
with each message type as a distinct dataclass with to_bytes() for serialization
and from_bytes() for parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct
from typing import TYPE_CHECKING

from .const import (
    DUO_FIRMWARE_STATUS_INTERVAL,
    FIRMWARE_HEADER_SIZE,
    FIRMWARE_STATUS_INTERVAL,
    FLIC2_FIRMWARE_IV_SIZE,
    FLIC2_FIRMWARE_STATUS_INTERVAL,
    OPCODE_ENABLE_PUSH_TWIST_IND,
    OPCODE_FIRMWARE_UPDATE_DATA_DUO_IND,
    OPCODE_FIRMWARE_UPDATE_DATA_IND,
    OPCODE_FORCE_BT_DISCONNECT_IND,
    OPCODE_FULL_VERIFY_REQUEST_1,
    OPCODE_FULL_VERIFY_REQUEST_2,
    OPCODE_INIT_BUTTON_EVENTS_DUO_REQUEST,
    OPCODE_INIT_BUTTON_EVENTS_REQUEST,
    OPCODE_QUICK_VERIFY_REQUEST,
    OPCODE_START_FIRMWARE_UPDATE_DUO_REQUEST,
    OPCODE_START_FIRMWARE_UPDATE_REQUEST,
    TWIST_OPCODE_ACK_BUTTON_EVENTS,
    TWIST_OPCODE_FIRMWARE_UPDATE_DATA_IND,
    TWIST_OPCODE_FORCE_BT_DISCONNECT_IND,
    TWIST_OPCODE_FULL_VERIFY_REQUEST_1,
    TWIST_OPCODE_FULL_VERIFY_REQUEST_2,
    TWIST_OPCODE_INIT_BUTTON_EVENTS,
    TWIST_OPCODE_QUICK_VERIFY_REQUEST,
    TWIST_OPCODE_START_FIRMWARE_UPDATE_REQUEST,
    TWIST_OPCODE_UPDATE_TWIST_POS,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class ButtonEventType(IntEnum):
    """Flic Duo button event types (3-bit encoding, 0-7)."""

    UP_SIMPLE = 0  # Button released (no gesture)
    UP_SINGLE_CLICK = 1  # Single click completed
    UP_AFTER_HOLD = 2  # Released after hold
    UP_DOUBLE_CLICK = 3  # Native double click!
    UP_WITH_FLAG = 4  # Double click that was also a hold
    DOWN = 5  # Button pressed
    SINGLE_CLICK_TIMEOUT = 6  # Single click confirmed (timeout)
    HOLD = 7  # Button held


class Gesture(IntEnum):
    """Flic Duo gesture directions (swipe/flick directions)."""

    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4


# =============================================================================
# Request Messages (sent to Flic button)
# =============================================================================


@dataclass
class FullVerifyRequest1:
    """Full verify request step 1 - initiates pairing."""

    tmp_id: int
    connection_id: int = 0

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        return struct.pack(
            "<BBI", frame_header, OPCODE_FULL_VERIFY_REQUEST_1, self.tmp_id
        )


@dataclass
class FullVerifyRequest2:
    """Full verify request step 2 - completes pairing with ECDH exchange."""

    connection_id: int
    ecdh_public_key: bytes
    client_random: bytes
    signature_variant: int
    supports_duo: bool
    verifier: bytes

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        # Flags byte: signatureVariant (3 bits) | encryptionVariant (3 bits) |
        # mustValidate (1 bit) | supportsDuo (1 bit)
        # Per SDK: signatureVariant=0, encryptionVariant=0 for request
        flags = (
            (0 & 0x07) | (0x00 << 3) | (0 << 6) | ((1 if self.supports_duo else 0) << 7)
        )

        frame_header = self.connection_id & 0x1F
        return (
            struct.pack("<BB", frame_header, OPCODE_FULL_VERIFY_REQUEST_2)
            + self.ecdh_public_key  # 32 bytes
            + self.client_random  # 8 bytes
            + struct.pack("<B", flags)  # 1 byte
            + self.verifier  # 16 bytes
        )


@dataclass
class QuickVerifyRequest:
    """Quick verify request - authenticates using stored credentials."""

    connection_id: int
    tmp_id: int
    pairing_id: int
    client_random: bytes  # 7 bytes
    supports_duo: bool = True

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        # flags: signatureVariant(3) | encryptionVariant(3) | supportsDuo(1)
        flags = 0x40 if self.supports_duo else 0x00  # bit 6 = supportsDuo

        frame_header = self.connection_id & 0x1F
        return struct.pack(
            "<BB7sBII",
            frame_header,
            OPCODE_QUICK_VERIFY_REQUEST,
            self.client_random,
            flags,
            self.tmp_id,
            self.pairing_id,
        )


@dataclass
class InitButtonEventsRequest:
    """Initialize button events request for Flic 2 (non-Duo)."""

    connection_id: int
    event_count: int = 0  # 0 = all new events
    boot_id: int = 0  # 0 = ignore boot id
    auto_disconnect_time: int = 0  # 0 = no auto-disconnect (9 bits)
    max_queued_packets: int = 30  # max 31 (5 bits)
    max_queued_packets_age: int = 60  # seconds (20 bits)

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        # Pack bit fields per SDK
        rfu = 0  # reserved
        packed_bits = (
            (self.auto_disconnect_time & 0x1FF)
            | ((self.max_queued_packets & 0x1F) << 9)
            | ((self.max_queued_packets_age & 0xFFFFF) << 14)
            | ((rfu & 0x3F) << 34)
        )

        return struct.pack(
            "<BBIIQ",
            self.connection_id & 0x1F,
            OPCODE_INIT_BUTTON_EVENTS_REQUEST,
            self.event_count,
            self.boot_id,
            packed_bits,
        )


@dataclass
class InitButtonEventsDuoRequest:
    """Initialize button events request for Flic Duo (Light version).

    Matches SDK's InitButtonEventsDuoLightRequest format.
    """

    connection_id: int
    event_count_0: int = 0  # Event count for button 0
    event_count_1: int = 0  # Event count for button 1
    boot_id: int = 0
    auto_disconnect_time: int = 0
    max_queued_packets: int = 30
    max_queued_packets_age: int = 60

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        # Pack bit fields into 8 bytes (64 bits)
        # autoDisconnectTime: 9 bits, maxQueuedPackets: 5 bits,
        # maxQueuedPacketsAge: 20 bits, rfu: 6 bits
        rfu = 0
        packed_bits = (
            (self.auto_disconnect_time & 0x1FF)
            | ((self.max_queued_packets & 0x1F) << 9)
            | ((self.max_queued_packets_age & 0xFFFFF) << 14)
            | ((rfu & 0x3F) << 34)
        )

        return struct.pack(
            "<BBIIIQ",
            self.connection_id & 0x1F,
            OPCODE_INIT_BUTTON_EVENTS_DUO_REQUEST,
            self.event_count_0,
            self.event_count_1,
            self.boot_id,
            packed_bits,
        )


@dataclass
class EnablePushTwistRequest:
    """Enable push twist (rotation) events for Flic Duo.

    This enables the button to send rotation data when the dial is turned
    while a button is pressed.
    """

    connection_id: int
    enable_button_0: bool = True
    enable_button_1: bool = True

    def to_bytes(self) -> bytes:
        """Serialize to bytes.

        Packs boolean flags into a single byte (each button = 1 bit).
        """
        flags = (1 if self.enable_button_0 else 0) | (
            (1 if self.enable_button_1 else 0) << 1
        )
        return struct.pack(
            "<BBB",
            self.connection_id & 0x1F,
            OPCODE_ENABLE_PUSH_TWIST_IND,
            flags,
        )


# =============================================================================
# Response Messages (received from Flic button)
# =============================================================================


@dataclass
class FullVerifyResponse1:
    """Full verify response step 1 - contains button identity and ECDH public key."""

    connection_id: int
    newly_assigned: bool
    tmp_id: int
    signature: bytes  # 64 bytes
    button_address: bytes  # 6 bytes
    address_type: int
    button_pubkey: bytes  # 32 bytes
    device_random: bytes  # 8 bytes
    flags: int
    is_duo: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> FullVerifyResponse1:
        """Parse from bytes."""
        # Header (1) | Opcode (1) | tmpId (4) | Signature (64) | Address (6) |
        # AddressType (1) | ECDH PubKey (32) | Random (8) | flags (1)
        expected_len = 1 + 1 + 4 + 64 + 6 + 1 + 32 + 8 + 1  # 118 bytes
        if len(data) < expected_len:
            raise ValueError(
                f"Invalid FullVerifyResponse1 length: {len(data)} (expected {expected_len})"
            )

        header = data[0]
        connection_id = header & 0x1F
        newly_assigned = bool(header & 0x20)

        offset = 2  # Skip header and opcode
        tmp_id = struct.unpack("<I", data[offset : offset + 4])[0]
        offset += 4

        signature = data[offset : offset + 64]
        offset += 64

        button_address = data[offset : offset + 6]
        offset += 6

        address_type = data[offset]
        offset += 1

        button_pubkey = data[offset : offset + 32]
        offset += 32

        device_random = data[offset : offset + 8]
        offset += 8

        flags = data[offset]
        # flags bit 0 = supportsDuo from button
        is_duo = bool(flags & 0x01)

        return cls(
            connection_id=connection_id,
            newly_assigned=newly_assigned,
            tmp_id=tmp_id,
            signature=signature,
            button_address=button_address,
            address_type=address_type,
            button_pubkey=button_pubkey,
            device_random=device_random,
            flags=flags,
            is_duo=is_duo,
        )


@dataclass
class FullVerifyResponse2:
    """Full verify response step 2 - pairing confirmation.

    Contains button metadata including serial number and Duo flag.
    Format per SDK:
    - opcode (1 byte)
    - flags (1 byte): bit 0=appCredentialsMatch, bit 1=caresAbout, bit 2=isDuo
    - buttonUuid (16 bytes)
    - nameLen (1 byte) + name (padded to 23 bytes)
    - firmwareVersion (4 bytes, u32 LE)
    - batteryLevel (2 bytes, u16 LE)
    - serialNumber (11 bytes, null-terminated)
    - pairingIdentifier (4 bytes, optional)
    - pairingKeyVariant (1 byte, optional)
    """

    connection_id: int
    newly_assigned: bool
    is_duo: bool
    button_uuid: bytes
    name: str
    firmware_version: int
    battery_level: int
    serial_number: str
    pairing_identifier: int | None
    pairing_key_variant: int | None

    @classmethod
    def from_bytes(cls, data: bytes) -> FullVerifyResponse2:
        """Parse from bytes."""
        # Minimum: header(1) + opcode(1) + flags(1) + uuid(16) + nameLen(1) + name(23)
        #          + firmware(4) + battery(2) + serial(11) = 60 bytes
        if len(data) < 60:
            raise ValueError(f"Invalid FullVerifyResponse2 length: {len(data)}")

        header = data[0]
        connection_id = header & 0x1F
        newly_assigned = bool(header & 0x20)

        # Skip opcode (data[1]), parse flags (data[2])
        flags = data[2]
        is_duo = bool(flags & 0x04)  # bit 2 = isDuo

        # Parse buttonUuid (16 bytes)
        button_uuid = data[3:19]

        # Parse name (1 byte length + up to 23 bytes padded)
        name_len = data[19]
        name = data[20 : 20 + name_len].decode("utf-8", errors="replace")
        # Skip name padding (23 - name_len bytes)

        # Parse firmware version (4 bytes LE) at offset 43
        firmware_version = struct.unpack("<I", data[43:47])[0]

        # Parse battery level (2 bytes LE) at offset 47
        battery_level = struct.unpack("<H", data[47:49])[0]

        # Parse serial number (11 bytes, null-terminated) at offset 49
        serial_bytes = data[49:60]
        # Find null terminator
        null_idx = serial_bytes.find(b"\x00")
        if null_idx >= 0:
            serial_number = serial_bytes[:null_idx].decode("utf-8", errors="replace")
        else:
            serial_number = serial_bytes.decode("utf-8", errors="replace")

        # Optional: pairingIdentifier (4 bytes) and pairingKeyVariant (1 byte)
        pairing_identifier = None
        pairing_key_variant = None
        if len(data) >= 64:
            pairing_identifier = struct.unpack("<I", data[60:64])[0]
        if len(data) >= 65:
            pairing_key_variant = data[64]

        return cls(
            connection_id=connection_id,
            newly_assigned=newly_assigned,
            is_duo=is_duo,
            button_uuid=button_uuid,
            name=name,
            firmware_version=firmware_version,
            battery_level=battery_level,
            serial_number=serial_number,
            pairing_identifier=pairing_identifier,
            pairing_key_variant=pairing_key_variant,
        )


@dataclass
class QuickVerifyResponse:
    """Quick verify response - contains button random for session key derivation."""

    connection_id: int
    newly_assigned: bool
    button_random: bytes  # 8 bytes
    tmp_id: int
    flags: int
    is_duo: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> QuickVerifyResponse:
        """Parse from bytes."""
        # frame_header (1) + opcode (1) + randomButtonBytes (8) + tmpId (4) + flags (1)
        if len(data) < 15:
            raise ValueError(
                f"Invalid QuickVerifyResponse: {len(data)} bytes (expected 15)"
            )

        header = data[0]
        connection_id = header & 0x1F
        newly_assigned = bool(header & 0x20)

        button_random = data[2:10]
        tmp_id = struct.unpack("<I", data[10:14])[0]
        flags = data[14]

        # flags bit 6 = supportsDuo
        is_duo = bool(flags & 0x40)

        return cls(
            connection_id=connection_id,
            newly_assigned=newly_assigned,
            button_random=button_random,
            tmp_id=tmp_id,
            flags=flags,
            is_duo=is_duo,
        )


@dataclass
class BatteryLevelResponse:
    """Battery level response."""

    battery_level: int  # 0..1024, voltage = level * 3.6 / 1024.0

    @classmethod
    def from_bytes(cls, data: bytes) -> BatteryLevelResponse:
        """Parse from bytes."""
        if len(data) < 3:
            raise ValueError("Invalid battery response")

        # Skip opcode, parse u16 battery level
        battery_level = struct.unpack("<H", data[1:3])[0]
        return cls(battery_level=battery_level)


@dataclass
class PushTwistDataNotification:
    """Push twist (rotation) data notification from Flic Duo.

    Sent when the dial is rotated while a button is pressed.
    Format per SDK (ResponseMessage.kt):
    - opcode (1 byte)
    - flags (1 byte):
        - bits 0-1: buttonsPressed (which buttons are currently pressed)
        - bits 2-3: isFirstEvent (first event since button press)
        - bits 4-5: buttonsPressedForAtLeastHalfASecond
        - bits 6-7: padding
    - angleDiff (4 bytes, signed int32 LE): rotation delta in units (4096 per detent)
    """

    buttons_pressed: (
        int  # bits 0-1: which buttons are pressed (0=none, 1=btn0, 2=btn1, 3=both)
    )
    is_first_event: int  # bits 2-3: first event flags
    buttons_pressed_half_second: int  # bits 4-5: pressed for at least 0.5s
    angle_diff: int  # signed int32: rotation delta

    @classmethod
    def from_bytes(cls, data: bytes) -> PushTwistDataNotification:
        """Parse from bytes (after header, includes opcode).

        Args:
            data: Packet data starting from opcode byte

        """
        # Minimum: opcode(1) + flags(1) + angleDiff(4) = 6 bytes
        if len(data) < 6:
            raise ValueError(
                f"Invalid PushTwistDataNotification length: {len(data)} (expected 6)"
            )

        # Skip opcode (data[0]), parse flags (data[1])
        flags = data[1]
        buttons_pressed = flags & 0x03
        is_first_event = (flags >> 2) & 0x03
        buttons_pressed_half_second = (flags >> 4) & 0x03

        # Parse angleDiff (signed int32 little-endian)
        angle_diff = struct.unpack("<i", data[2:6])[0]

        return cls(
            buttons_pressed=buttons_pressed,
            is_first_event=is_first_event,
            buttons_pressed_half_second=buttons_pressed_half_second,
            angle_diff=angle_diff,
        )


# =============================================================================
# Button Event Types
# =============================================================================


@dataclass
class Flic2ButtonEvent:
    """Flic 2 (non-Duo) button event.

    Parsed from 7-byte slots with bit-packed data:
    - 48 bits: timestamp in Bluetooth time (ticks at 32768 Hz)
    - 4 bits: eventEncoded (0-3)
    - 1 bit: wasQueued
    - 1 bit: wasQueuedLast
    - 2 bits: padding
    """

    timestamp_ms: int
    event_type: int  # 0=UP, 1=DOWN, 2=SINGLE_CLICK_TIMEOUT, 3=HOLD
    was_queued: bool
    was_queued_last: bool

    @classmethod
    def from_slot_bytes(cls, slot_data: bytes) -> Flic2ButtonEvent:
        """Parse from 7-byte slot."""
        if len(slot_data) != 7:
            raise ValueError(f"Invalid slot size: {len(slot_data)} (expected 7)")

        # Bytes 0-5: 48-bit timestamp (LE) in 1/32768 second ticks
        timestamp_raw = int.from_bytes(slot_data[0:6], byteorder="little")
        timestamp_ms = timestamp_raw * 1000 // 32768

        # Byte 6: bits 0-3 = eventEncoded, bit 4 = wasQueued, bit 5 = wasQueuedLast
        flags_byte = slot_data[6]
        event_type = flags_byte & 0x0F
        was_queued = bool(flags_byte & 0x10)
        was_queued_last = bool(flags_byte & 0x20)

        return cls(
            timestamp_ms=timestamp_ms,
            event_type=event_type,
            was_queued=was_queued,
            was_queued_last=was_queued_last,
        )


@dataclass
class FlicDuoButtonEvent:
    """Flic Duo button event with extended types.

    Duo events use a variable-length bit-packed format with 3-bit event encoding
    and support for native double click, gestures, and accelerometer data.
    """

    button_index: int  # 0 or 1 for Duo
    timestamp_ms: int
    event_type: ButtonEventType
    double_click_was_hold: bool
    next_up_will_be_double_click: bool
    gesture: Gesture | None
    accel_x: int
    accel_y: int
    accel_z: int
    was_queued: bool
    was_queued_last: bool


class DuoParserState:
    """Parser state for Flic Duo event stream.

    The Duo protocol uses delta compression for timestamps and event counts,
    requiring state to be maintained across event packets.
    """

    # Bit widths for event counter delta encoding
    COUNTER_EXTRA_BITS = [2, 4, 8, 32]
    # Bit widths for timestamp delta encoding (indexed by 3-bit value)
    TS_DELTA_BITS = [8, 10, 13, 16, 24, 32, 40, 48]

    def __init__(self) -> None:
        """Initialize parser state."""
        self.last_timestamp: int = 0
        self.event_count: list[int] = [0, 0]  # Per-button event counts
        self.has_processed_end_of_queue_marker: bool = False

    def copy_snapshot(self) -> tuple[int, list[int], bool]:
        """Create a snapshot of current state for rollback."""
        return (
            self.last_timestamp,
            self.event_count.copy(),
            self.has_processed_end_of_queue_marker,
        )

    def restore(self, snapshot: tuple[int, list[int], bool]) -> None:
        """Restore state from snapshot."""
        self.last_timestamp = snapshot[0]
        self.event_count = snapshot[1].copy()
        self.has_processed_end_of_queue_marker = snapshot[2]

    def reset(self) -> None:
        """Reset parser state."""
        self.last_timestamp = 0
        self.event_count = [0, 0]
        self.has_processed_end_of_queue_marker = False

    def initialize(
        self,
        event_counts: list[int],
        last_timestamp: int,
        has_processed_end_of_queue_marker: bool,
    ) -> None:
        """Initialize parser state with known values."""
        self.event_count = event_counts.copy()
        self.last_timestamp = last_timestamp
        self.has_processed_end_of_queue_marker = has_processed_end_of_queue_marker


@dataclass
class Flic2EventNotification:
    """Flic 2 (non-Duo) button event notification containing multiple events."""

    event_count: int
    events: list[Flic2ButtonEvent]

    @classmethod
    def from_bytes(cls, data: bytes) -> Flic2EventNotification:
        """Parse button event notification from bytes (after opcode).

        Args:
            data: Event data after opcode (includes eventCount + events)

        """
        if len(data) < 4:
            raise ValueError(f"Button event data too short: {len(data)} bytes")

        # Parse eventCount (first 4 bytes)
        event_count = struct.unpack("<I", data[0:4])[0]
        event_bytes = data[4:]

        events: list[Flic2ButtonEvent] = []

        # Parse events in 7-byte slots
        num_slots = len(event_bytes) // 7
        for slot_idx in range(num_slots):
            slot_data = event_bytes[slot_idx * 7 : (slot_idx + 1) * 7]
            events.append(Flic2ButtonEvent.from_slot_bytes(slot_data))

        return cls(event_count=event_count, events=events)


@dataclass
class FlicDuoEventNotification:
    """Flic Duo button event notification containing multiple events.

    The Duo format is bit-packed with variable-length events following the SDK:
    - buttonIndex: 1 bit
    - eventCounterDelta: variable (1 bit + optional 2-bit index + variable bits)
    - timestampDelta: 3-bit index into [8,10,13,16,24,32,40,48] + that many bits
    - queueMarkers: conditional tree based on hasProcessedEndOfQueueMarker
    - eventType: 3 bits
    - Conditional flags based on eventType
    - gestureData: conditional (1 bit reported + 1 bit recognized + 2 bits direction)
    - accelerometer: 3 signed bytes (always present)
    """

    per_button_event_count: list[int]
    events: list[FlicDuoButtonEvent]
    needs_ack: bool
    has_processed_end_of_queue_marker: bool
    has_parse_error: bool = False

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        parser_state: DuoParserState | None = None,
    ) -> FlicDuoEventNotification:
        """Parse Duo button event notification from bytes.

        Args:
            data: Event data after opcode (raw event bytes, no count prefix)
            parser_state: Parser state for delta timestamps and event counts

        """
        if parser_state is None:
            parser_state = DuoParserState()

        if len(data) < 1:
            return cls(
                per_button_event_count=parser_state.event_count.copy(),
                events=[],
                needs_ack=False,
                has_processed_end_of_queue_marker=(
                    parser_state.has_processed_end_of_queue_marker
                ),
            )

        events, per_button_counts, needs_ack, has_error = _parse_duo_events_from_bytes(
            data, parser_state
        )

        return cls(
            per_button_event_count=per_button_counts,
            events=events,
            needs_ack=needs_ack,
            has_processed_end_of_queue_marker=(
                parser_state.has_processed_end_of_queue_marker
            ),
            has_parse_error=has_error,
        )


class UnexpectedEndOfPacketError(Exception):
    """Raised when packet data ends unexpectedly during parsing."""


class _BitReader:
    """Bit reader for parsing bit-packed Duo events.

    Matches the Kotlin SDK BitReader implementation for correct parsing.
    """

    def __init__(self, data: bytes) -> None:
        """Initialize bit reader."""
        self._data = data
        self._pos = 0
        self._bitpos = 0

    @property
    def bits_remaining(self) -> int:
        """Return remaining bits."""
        return (len(self._data) * 8) - (self._pos * 8 + self._bitpos)

    def read_bits(self, width: int) -> int:
        """Read n bits and return as integer (little-endian bit order).

        This matches the Kotlin SDK bits() method.
        """
        if width > 8:
            low = self.read_bits(8)
            high = self.read_bits(width - 8)
            return low | (high << 8)

        if self._bitpos == 0:
            if self._pos >= len(self._data):
                raise UnexpectedEndOfPacketError
            value = (self._data[self._pos] & 0xFF) & ((1 << width) - 1)
            self._pos += 1
            if width != 8:
                self._bitpos = width
            return value
        value = ((self._data[self._pos - 1] & 0xFF) >> self._bitpos) & (
            (1 << width) - 1
        )
        if self._bitpos + width > 8:
            if self._pos >= len(self._data):
                raise UnexpectedEndOfPacketError
            value = value | (
                ((self._data[self._pos] & 0xFF) << (8 - self._bitpos))
                & ((1 << width) - 1)
            )
            self._pos += 1
            self._bitpos -= 8
        self._bitpos += width
        if self._bitpos == 8:
            self._bitpos = 0
        return value

    def read_bool(self) -> bool:
        """Read a single bit as boolean."""
        return self.read_bits(1) != 0

    def read_signed_byte(self) -> int:
        """Read 8 bits as signed byte (-128 to 127)."""
        value = self.read_bits(8)
        if value >= 128:
            return value - 256
        return value


def _parse_duo_events_from_bytes(
    data: bytes,
    state: DuoParserState,
) -> tuple[list[FlicDuoButtonEvent], list[int], bool, bool]:
    """Parse Duo events from byte data following SDK protocol.

    Returns:
        Tuple of (events, per_button_event_counts, needs_ack, has_parse_error)
    """
    reader = _BitReader(data)
    events: list[FlicDuoButtonEvent] = []
    got_event_count = [False, False]
    send_ack = False
    had_parse_error = False

    # Need at least 39 bits for minimum event
    while reader.bits_remaining >= 39:
        snapshot = state.copy_snapshot()
        got_event_snapshot = got_event_count.copy()

        try:
            # 1 bit: button index (0 or 1)
            button_index = reader.read_bits(1)

            # Variable-length event counter delta
            if not got_event_count[button_index]:
                event_counter_delta = reader.read_bits(1)
                if event_counter_delta > 0 and reader.read_bool():
                    num_bits_index = reader.read_bits(2)
                    num_bits = DuoParserState.COUNTER_EXTRA_BITS[num_bits_index]
                    event_counter_delta = reader.read_bits(num_bits)
                event_counter_delta += 1
                state.event_count[button_index] += event_counter_delta
                got_event_count[button_index] = True
            else:
                state.event_count[button_index] += 1

            # Variable-length timestamp delta
            timestamp_num_bits_index = reader.read_bits(3)
            timestamp_num_bits = DuoParserState.TS_DELTA_BITS[timestamp_num_bits_index]
            timestamp_delta = reader.read_bits(timestamp_num_bits)
            state.last_timestamp += timestamp_delta

            # Queue markers (conditional tree)
            was_queued = False
            was_queued_last = False

            if not state.has_processed_end_of_queue_marker:
                if not reader.read_bool():
                    # This event does not mark end of queue
                    was_queued = True
                else:
                    # Found end of queue
                    state.has_processed_end_of_queue_marker = True
                    if not reader.read_bool():
                        # This event is the last event queued
                        was_queued = True
                        was_queued_last = True
                    # else: discarded event at queue end

            # Event type: 3 bits
            type_bits = reader.read_bits(3)

            # Additional flags based on type
            up_extra = False
            next_up_will_be_double_click = False

            if type_bits == 4:  # UP_WITH_FLAG
                up_extra = reader.read_bool()
            elif type_bits == 7:  # HOLD
                next_up_will_be_double_click = reader.read_bool()

            # Gesture data (for Up types 0-4 or SingleClickTimeout type 6)
            gesture: Gesture | None = None

            if (type_bits <= 4 or type_bits == 6) and reader.read_bool():
                # gesture reported
                if reader.read_bool():  # gesture recognized
                    gesture_dir = reader.read_bits(2) + 1  # 1..4
                    # Map to Gesture enum (1=LEFT, 2=RIGHT, 3=UP, 4=DOWN)
                    gesture = Gesture(gesture_dir) if 1 <= gesture_dir <= 4 else None
                # else: unrecognized gesture (gestureData = 0)

            # Accelerometer data (always 3 signed bytes)
            accel_x = reader.read_signed_byte()
            accel_y = reader.read_signed_byte()
            accel_z = reader.read_signed_byte()

            # Event counter parity adjustment
            # "Up or down was not preceded by hold or single click timeout"
            if type_bits <= 5 and state.event_count[button_index] % 2 == 0:
                state.event_count[button_index] += 1

            # Determine event type
            try:
                event_type = ButtonEventType(type_bits)
            except ValueError:
                # Unknown event type
                had_parse_error = True
                break

            # Set ACK flag for single and double clicks
            if event_type in (
                ButtonEventType.UP_SINGLE_CLICK,
                ButtonEventType.UP_DOUBLE_CLICK,
                ButtonEventType.SINGLE_CLICK_TIMEOUT,
            ):
                send_ack = True

            # Calculate double_click_was_hold for UP_WITH_FLAG or UP_AFTER_HOLD
            was_hold = type_bits == 2 or (type_bits == 4 and up_extra)
            double_click = type_bits in {3, 4}
            double_click_was_hold = was_hold and double_click

            events.append(
                FlicDuoButtonEvent(
                    button_index=button_index,
                    timestamp_ms=state.last_timestamp,
                    event_type=event_type,
                    double_click_was_hold=double_click_was_hold,
                    next_up_will_be_double_click=next_up_will_be_double_click,
                    gesture=gesture,
                    accel_x=accel_x,
                    accel_y=accel_y,
                    accel_z=accel_z,
                    was_queued=was_queued,
                    was_queued_last=was_queued_last,
                )
            )

        except UnexpectedEndOfPacketError:
            # Ran out of bits - rollback state
            if not events:
                had_parse_error = True
            state.restore(snapshot)
            got_event_count = got_event_snapshot
            break
        except ValueError, IndexError:
            state.restore(snapshot)
            got_event_count = got_event_snapshot
            had_parse_error = True
            break

    return events, state.event_count.copy(), send_ack, had_parse_error


def parse_flic2_events(event_data: bytes) -> Sequence[Flic2ButtonEvent]:
    """Parse Flic 2 button events from notification data.

    Args:
        event_data: Event data after opcode

    Returns:
        List of parsed button events

    """
    notification = Flic2EventNotification.from_bytes(event_data)
    return notification.events


def parse_duo_events(
    event_data: bytes,
    parser_state: DuoParserState | None = None,
) -> tuple[Sequence[FlicDuoButtonEvent], FlicDuoEventNotification]:
    """Parse Flic Duo button events from notification data.

    Args:
        event_data: Event data after opcode (raw event bytes)
        parser_state: Parser state for delta timestamps and event counts

    Returns:
        Tuple of (parsed button events, full notification with metadata)

    """
    notification = FlicDuoEventNotification.from_bytes(event_data, parser_state)
    return notification.events, notification


# =============================================================================
# Flic Twist Protocol Messages
# =============================================================================
# Twist uses a simpler packet framing than Flic 2/Duo:
# - No frame header (no connId, no fragment flags)
# - Format: [opcode:1][payload:N][mac:5 if session active]
# - Session is active immediately after Quick/Full Verify (no "newlyAssigned" step)


@dataclass
class TwistModeConfig:
    """Configuration for a single Twist mode (one of 13 modes).

    Modes:
        0-11: Individual slot positions
        12: Slot-changing mode (free rotation to select active slot)
    """

    led_mode: int  # 0-3 (6 bits used in protocol)
    has_click: bool
    has_double_click: bool
    extra_leds_after: int  # 0-15 (4 bits)
    position: int  # 0..49152 (current rotation position)
    timeout_seconds: int  # 0..255, 255=infinite

    def to_bytes(self) -> bytes:
        """Serialize mode config to bytes.

        Format (5 bytes per SDK InitButtonEventsRequestV2.TwistStateConfig):
        - packed 32-bit LE:
            bits 0-5: ledMode (6 bits)
            bit 6: hasClick
            bit 7: hasDoubleClick
            bits 8-11: extraLedsAfter (4 bits)
            bits 12-15: padding (0)
            bits 16-31: position (16 bits)
        - timeout_seconds (1 byte)
        """
        packed = (
            (self.led_mode & 0x3F)
            | ((1 if self.has_click else 0) << 6)
            | ((1 if self.has_double_click else 0) << 7)
            | ((self.extra_leds_after & 0x0F) << 8)
            | ((self.position & 0xFFFF) << 16)
        )
        return struct.pack("<IB", packed, self.timeout_seconds)


@dataclass
class TwistFullVerifyRequest1:
    """Twist full verify request step 1 - initiates pairing.

    Twist uses simpler framing - no connection ID in header.
    """

    tmp_id: int

    def to_bytes(self) -> bytes:
        """Serialize to bytes (no frame header for Twist)."""
        return struct.pack("<BI", TWIST_OPCODE_FULL_VERIFY_REQUEST_1, self.tmp_id)


@dataclass
class TwistFullVerifyRequest2:
    """Twist full verify request step 2 - completes pairing with ECDH exchange."""

    ecdh_public_key: bytes  # 32 bytes
    client_random: bytes  # 8 bytes
    signature_variant: int  # 3 bits (0-7), but SDK always sends 0
    encryption_variant: int = 0  # 3 bits (0-7), SDK always sends 0
    must_validate_app_token: bool = False  # 1 bit, SDK always sends False
    verifier: bytes = b""  # 16 bytes

    def to_bytes(self) -> bytes:
        """Serialize to bytes (no frame header for Twist)."""
        # Pack flags byte: signatureVariant(bits 0-2) | encryptionVariant(bits 3-5) | mustValidateAppToken(bit 6)
        flags = (
            (self.signature_variant & 0x07)
            | ((self.encryption_variant & 0x07) << 3)
            | (0x40 if self.must_validate_app_token else 0)
        )

        return (
            struct.pack("<B", TWIST_OPCODE_FULL_VERIFY_REQUEST_2)
            + self.ecdh_public_key  # 32 bytes
            + self.client_random  # 8 bytes
            + struct.pack("<B", flags)  # 1 byte
            + self.verifier  # 16 bytes
        )


@dataclass
class TwistQuickVerifyRequest:
    """Twist quick verify request - authenticates using stored credentials."""

    tmp_id: int
    pairing_id: int
    client_random: bytes  # 7 bytes
    signature_variant: int = 0  # 3 bits (sigBits from full verify)
    encryption_variant: int = 0  # 3 bits (0 = no encryption)

    def to_bytes(self) -> bytes:
        """Serialize to bytes (no frame header for Twist).

        Format (17 bytes):
        - opcode (1 byte)
        - client_random (7 bytes)
        - packed byte: signatureVariant (bits 0-2) + encryptionVariant (bits 3-5)
        - tmp_id (4 bytes, UInt32 LE)
        - pairing_id (4 bytes, UInt32 LE)
        """
        packed = (self.signature_variant & 0x07) | (
            (self.encryption_variant & 0x07) << 3
        )
        return struct.pack(
            "<B7sBII",
            TWIST_OPCODE_QUICK_VERIFY_REQUEST,
            self.client_random,
            packed,
            self.tmp_id,
            self.pairing_id,
        )


@dataclass
class TwistFullVerifyResponse1:
    """Twist full verify response step 1 - contains button identity and ECDH public key."""

    tmp_id: int
    signature: bytes  # 64 bytes
    button_address: bytes  # 6 bytes
    address_type: int
    button_pubkey: bytes  # 32 bytes
    device_random: bytes  # 8 bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> TwistFullVerifyResponse1:
        """Parse from bytes (no frame header in Twist)."""
        # Opcode (1) | tmpId (4) | Signature (64) | Address (6) |
        # AddressType (1) | ECDH PubKey (32) | Random (8)
        expected_len = 1 + 4 + 64 + 6 + 1 + 32 + 8  # 116 bytes
        if len(data) < expected_len:
            raise ValueError(
                f"Invalid TwistFullVerifyResponse1 length: {len(data)} (expected {expected_len})"
            )

        offset = 1  # Skip opcode
        tmp_id = struct.unpack("<I", data[offset : offset + 4])[0]
        offset += 4

        signature = data[offset : offset + 64]
        offset += 64

        button_address = data[offset : offset + 6]
        offset += 6

        address_type = data[offset]
        offset += 1

        button_pubkey = data[offset : offset + 32]
        offset += 32

        device_random = data[offset : offset + 8]

        return cls(
            tmp_id=tmp_id,
            signature=signature,
            button_address=button_address,
            address_type=address_type,
            button_pubkey=button_pubkey,
            device_random=device_random,
        )


@dataclass
class TwistFullVerifyResponse2:
    """Twist full verify response step 2 - pairing confirmation."""

    button_uuid: bytes  # 16 bytes
    name: str
    firmware_version: int
    battery_level: int
    serial_number: str
    color: str
    app_credentials_match: bool
    cares_about_app_credentials: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> TwistFullVerifyResponse2:
        """Parse from bytes (no frame header in Twist).

        Format (75 bytes total):
        - opcode (1 byte) at offset 0
        - flags (1 byte) at offset 1
        - button_uuid (16 bytes) at offset 2
        - name_len (1 byte) at offset 18
        - name (23 bytes padded) at offset 19
        - firmware_version (4 bytes LE) at offset 42
        - battery_level (2 bytes LE) at offset 46
        - serial_number (11 bytes) at offset 48
        - color (16 bytes) at offset 59
        """
        if len(data) < 75:
            raise ValueError(f"Invalid TwistFullVerifyResponse2 length: {len(data)}")

        # Skip opcode (data[0])
        flags = data[1]
        app_credentials_match = bool(flags & 0x01)
        cares_about_app_credentials = bool(flags & 0x02)

        button_uuid = data[2:18]

        name_len = data[18]
        name = data[19 : 19 + name_len].decode("utf-8", errors="replace")

        # firmware at offset 42 (1 + 1 + 16 + 1 + 23)
        firmware_version = struct.unpack("<I", data[42:46])[0]
        battery_level = struct.unpack("<H", data[46:48])[0]

        # serial at offset 48
        serial_bytes = data[48:59]
        null_idx = serial_bytes.find(b"\x00")
        if null_idx >= 0:
            serial_number = serial_bytes[:null_idx].decode("utf-8", errors="replace")
        else:
            serial_number = serial_bytes.decode("utf-8", errors="replace")

        # color at offset 59
        color_bytes = data[59:75]
        null_idx = color_bytes.find(b"\x00")
        if null_idx >= 0:
            color = color_bytes[:null_idx].decode("utf-8", errors="replace")
        else:
            color = color_bytes.decode("utf-8", errors="replace")

        return cls(
            button_uuid=button_uuid,
            name=name,
            firmware_version=firmware_version,
            battery_level=battery_level,
            serial_number=serial_number,
            color=color,
            app_credentials_match=app_credentials_match,
            cares_about_app_credentials=cares_about_app_credentials,
        )


@dataclass
class TwistQuickVerifyResponse:
    """Twist quick verify response - contains button random for session key derivation."""

    button_random: bytes  # 8 bytes
    tmp_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> TwistQuickVerifyResponse:
        """Parse from bytes (no frame header in Twist)."""
        # opcode (1) + buttonRandom (8) + tmpId (4)
        if len(data) < 13:
            raise ValueError(
                f"Invalid TwistQuickVerifyResponse: {len(data)} bytes (expected 13)"
            )

        button_random = data[1:9]
        tmp_id = struct.unpack("<I", data[9:13])[0]

        return cls(button_random=button_random, tmp_id=tmp_id)


@dataclass
class InitButtonEventsTwistRequest:
    """Initialize button events for Flic Twist (13 modes).

    Matches SDK's InitButtonEventsRequestV2 format.

    Twist has 13 twist modes, each with its own configuration:
    - Modes 0-11: Individual slot positions
    - Mode 12: Slot-changing mode (free rotation to select active slot)
    """

    mode_configs: list[TwistModeConfig]  # Must be exactly 13 items
    event_count: int = 0  # 0 = all new events
    boot_id: int = 0  # 0 = ignore boot id
    api_version: int = 2  # V2 format

    def to_bytes(self) -> bytes:
        """Serialize to bytes.

        Format (75 bytes per SDK):
        - opcode (1)
        - eventCount (4, u32 LE)
        - 13 configs × 5 bytes each = 65 bytes
        - bootId (4, u32 LE)
        - apiVersion (1)
        """
        if len(self.mode_configs) != 13:
            raise ValueError("Twist requires exactly 13 mode configs")

        # Build payload matching SDK InitButtonEventsRequestV2
        payload = bytearray()
        payload.append(TWIST_OPCODE_INIT_BUTTON_EVENTS)
        payload.extend(struct.pack("<I", self.event_count))

        for config in self.mode_configs:
            payload.extend(config.to_bytes())

        payload.extend(struct.pack("<I", self.boot_id))
        payload.append(self.api_version)

        return bytes(payload)


@dataclass
class TwistButtonEventV2:
    """Twist button event (V2 format with twist_mode_index).

    Twist button events include the current twist mode index.
    """

    timestamp_ms: int
    event_type: int  # Same as Flic 2: UP, DOWN, CLICK, HOLD, etc.
    twist_mode_index: int  # 0-12: current twist mode
    was_queued: bool
    was_queued_last: bool

    @classmethod
    def from_slot_bytes(cls, slot_data: bytes) -> TwistButtonEventV2:
        """Parse from 8-byte slot (V2 format with mode index)."""
        if len(slot_data) < 8:
            raise ValueError(f"Invalid Twist event slot size: {len(slot_data)}")

        # Bytes 0-5: 48-bit timestamp in 1/32768 second ticks
        timestamp_raw = int.from_bytes(slot_data[0:6], byteorder="little")
        timestamp_ms = timestamp_raw * 1000 // 32768

        # V2 bitfield layout (packed uint64_t, little-endian):
        #   bits 0-47:  timestamp (bytes 0-5)
        #   bits 48-51: event_encoded (byte 6, bits 0-3)
        #   bit 52:     was_queued (byte 6, bit 4)
        #   bit 53:     was_queued_last (byte 6, bit 5)
        #   bits 54-57: twist_mode_index (byte 6 bits 6-7 + byte 7 bits 0-1)
        #   bits 58-63: padding (byte 7, bits 2-7)
        flags_byte = slot_data[6]
        event_type = flags_byte & 0x0F
        was_queued = bool(flags_byte & 0x10)
        was_queued_last = bool(flags_byte & 0x20)

        # twist_mode_index spans bytes 6-7: lower 2 bits in byte 6 bits 6-7,
        # upper 2 bits in byte 7 bits 0-1
        twist_mode_index = ((flags_byte >> 6) & 0x03) | ((slot_data[7] & 0x03) << 2)

        return cls(
            timestamp_ms=timestamp_ms,
            event_type=event_type,
            twist_mode_index=twist_mode_index,
            was_queued=was_queued,
            was_queued_last=was_queued_last,
        )


@dataclass
class TwistEventNotification:
    """Twist rotation event from device.

    Sent when the Twist dial is rotated. Unlike Flic Duo (push+twist only),
    Twist sends rotation events in all 13 modes.

    Format per PROTOCOL.md:
    - twist_mode_index: 4 bits
    - last_min_update_was_top: 1 bit
    - last_hub_update_packet_too_old: 1 bit
    - total_delta: 24-bit signed
    - min_delta: 24-bit signed
    - max_delta: 24-bit signed
    - last_known_hub_packet_counter: u16
    """

    twist_mode_index: int  # 0-11=slots, 12=slot-changing
    total_delta: int  # 24-bit signed: total rotation since last event
    min_delta: int  # 24-bit signed: minimum rotation in this period
    max_delta: int  # 24-bit signed: maximum rotation in this period
    last_hub_packet_counter: int  # For sync protocol
    last_min_update_was_top: bool
    last_hub_update_packet_too_old: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> TwistEventNotification:
        """Parse from bytes (after opcode).

        Args:
            data: Event data starting from opcode byte

        """
        # Minimum: opcode(1) + flags(1) + total(3) + min(3) + max(3) + counter(2) = 13 bytes
        if len(data) < 13:
            raise ValueError(
                f"Invalid TwistEventNotification length: {len(data)} (expected 13)"
            )

        # Skip opcode (data[0]), parse flags (data[1])
        flags = data[1]
        twist_mode_index = flags & 0x0F
        last_min_update_was_top = bool(flags & 0x10)
        last_hub_update_packet_too_old = bool(flags & 0x20)

        # Parse 24-bit signed integers (little-endian)
        def parse_signed_24(b: bytes) -> int:
            value = int.from_bytes(b, byteorder="little")
            if value >= 0x800000:  # Sign extend
                value -= 0x1000000
            return value

        total_delta = parse_signed_24(data[2:5])
        min_delta = parse_signed_24(data[5:8])
        max_delta = parse_signed_24(data[8:11])
        last_hub_packet_counter = struct.unpack("<H", data[11:13])[0]

        return cls(
            twist_mode_index=twist_mode_index,
            total_delta=total_delta,
            min_delta=min_delta,
            max_delta=max_delta,
            last_hub_packet_counter=last_hub_packet_counter,
            last_min_update_was_top=last_min_update_was_top,
            last_hub_update_packet_too_old=last_hub_update_packet_too_old,
        )


@dataclass
class InitButtonEventsResponseV2:
    """Twist InitButtonEvents response (V2 format).

    Per spec:
    - opcode (1 byte)
    - has_queued_events: 1 bit
    - timestamp: 47 bits (RTC ticks at 32768 Hz)
    - event_count: u32
    - boot_id: u32
    - api_version: u8
    """

    has_queued_events: bool
    timestamp: int  # RTC ticks at 32768 Hz
    event_count: int
    boot_id: int
    api_version: int

    @classmethod
    def from_bytes(cls, data: bytes) -> InitButtonEventsResponseV2:
        """Parse from bytes (includes opcode)."""
        # Minimum: opcode(1) + flags+timestamp(6) + event_count(4) + boot_id(4) + api_version(1) = 16
        if len(data) < 16:
            raise ValueError(
                f"Invalid InitButtonEventsResponseV2 length: {len(data)} (expected 16)"
            )

        # Bytes 1-6: packed 48-bit field (1 bit has_queued + 47 bits timestamp)
        packed = int.from_bytes(data[1:7], byteorder="little")
        has_queued_events = bool(packed & 0x01)
        timestamp = (packed >> 1) & 0x7FFFFFFFFFFF  # 47 bits

        event_count = struct.unpack("<I", data[7:11])[0]
        boot_id = struct.unpack("<I", data[11:15])[0]
        api_version = data[15]

        return cls(
            has_queued_events=has_queued_events,
            timestamp=timestamp,
            event_count=event_count,
            boot_id=boot_id,
            api_version=api_version,
        )


@dataclass
class TwistButtonEventNotification:
    """Twist button event notification containing multiple V2 events."""

    event_count: int
    events: list[TwistButtonEventV2]

    @classmethod
    def from_bytes(cls, data: bytes) -> TwistButtonEventNotification:
        """Parse button event notification from bytes (after opcode).

        Args:
            data: Event data after opcode (includes eventCount + events)

        """
        if len(data) < 4:
            raise ValueError(f"Twist button event data too short: {len(data)} bytes")

        # Parse eventCount (first 4 bytes)
        event_count = struct.unpack("<I", data[0:4])[0]
        event_bytes = data[4:]

        events: list[TwistButtonEventV2] = []

        # Parse events in 8-byte slots (V2 format)
        num_slots = len(event_bytes) // 8
        for slot_idx in range(num_slots):
            slot_data = event_bytes[slot_idx * 8 : (slot_idx + 1) * 8]
            events.append(TwistButtonEventV2.from_slot_bytes(slot_data))

        return cls(event_count=event_count, events=events)


@dataclass
class UpdateTwistPositionRequest:
    """Update Twist position indication.

    Sent when the device reports last_hub_update_packet_too_old=true,
    to resync the position tracking.
    """

    twist_mode_index: int
    new_min: int  # 48-bit signed: new minimum position
    num_received_update_packets: int  # u32

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        # Pack 48-bit signed as 6 bytes little-endian
        new_min_bytes = (self.new_min & 0xFFFFFFFFFFFF).to_bytes(6, byteorder="little")

        return (
            struct.pack("<BB", TWIST_OPCODE_UPDATE_TWIST_POS, self.twist_mode_index)
            + new_min_bytes
            + struct.pack("<I", self.num_received_update_packets)
        )


@dataclass
class AckButtonEventsTwistRequest:
    """Acknowledge button events for Twist.

    Per spec: opcode (1 byte) + event_count (4 bytes, u32 LE).
    The event_count is the press_counter from the last processed event.
    """

    event_count: int  # press_counter from last processed event

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return struct.pack("<BI", TWIST_OPCODE_ACK_BUTTON_EVENTS, self.event_count)


# =============================================================================
# Firmware Update Messages
# =============================================================================


@dataclass
class StartFirmwareUpdateRequest:
    """Request to start a firmware update on a Twist device.

    The firmware binary has a 76-byte header:
    - iv (8 bytes): Initialization vector
    - length_uncompressed_words (4 bytes): Uncompressed size in 32-bit words
    - signature (64 bytes): Ed25519 signature
    Followed by the compressed firmware data.
    """

    length_compressed_bytes: int  # u32: length of compressed data
    iv: bytes  # 8 bytes
    length_uncompressed_words: int  # u32
    signature: bytes  # 64 bytes
    status_interval: int = FIRMWARE_STATUS_INTERVAL  # u16

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return (
            struct.pack(
                "<BI",
                TWIST_OPCODE_START_FIRMWARE_UPDATE_REQUEST,
                self.length_compressed_bytes,
            )
            + self.iv  # 8 bytes
            + struct.pack("<I", self.length_uncompressed_words)
            + self.signature  # 64 bytes
            + struct.pack("<H", self.status_interval)
        )

    @classmethod
    def from_firmware_binary(cls, firmware_binary: bytes) -> StartFirmwareUpdateRequest:
        """Create request from a firmware binary file.

        Args:
            firmware_binary: Raw firmware binary (header + compressed data)

        """
        if len(firmware_binary) < FIRMWARE_HEADER_SIZE:
            raise ValueError(
                f"Firmware binary too short: {len(firmware_binary)} bytes "
                f"(minimum {FIRMWARE_HEADER_SIZE})"
            )

        iv = firmware_binary[0:8]
        length_uncompressed_words = struct.unpack("<I", firmware_binary[8:12])[0]
        signature = firmware_binary[12:76]
        compressed_data = firmware_binary[FIRMWARE_HEADER_SIZE:]

        return cls(
            length_compressed_bytes=len(compressed_data),
            iv=iv,
            length_uncompressed_words=length_uncompressed_words,
            signature=signature,
        )


@dataclass
class StartFirmwareUpdateResponse:
    """Response to start firmware update request.

    start_pos values:
    - 0: Start from beginning (new update)
    - >0: Resume from this byte position
    - -1: Invalid parameters
    - -2: Device busy
    - -3: Pending reboot (previous update needs reboot)
    """

    start_pos: int  # i32 signed

    @classmethod
    def from_bytes(cls, data: bytes) -> StartFirmwareUpdateResponse:
        """Parse from bytes (includes opcode)."""
        if len(data) < 5:
            raise ValueError(f"Invalid StartFirmwareUpdateResponse length: {len(data)}")
        start_pos = struct.unpack("<i", data[1:5])[0]
        return cls(start_pos=start_pos)


@dataclass
class FirmwareUpdateNotification:
    """Progress notification during firmware transfer.

    pos values:
    - >0: Bytes acknowledged so far (progress)
    - ==total_compressed: Transfer complete
    - ==0: Signature verification failed
    """

    pos: int  # i32 signed

    @classmethod
    def from_bytes(cls, data: bytes) -> FirmwareUpdateNotification:
        """Parse from bytes (includes opcode)."""
        if len(data) < 5:
            raise ValueError(f"Invalid FirmwareUpdateNotification length: {len(data)}")
        pos = struct.unpack("<i", data[1:5])[0]
        return cls(pos=pos)


@dataclass
class FirmwareUpdateDataInd:
    """Firmware data chunk sent to device during OTA update."""

    chunk_data: bytes  # Up to FIRMWARE_DATA_CHUNK_SIZE bytes

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return (
            struct.pack("<B", TWIST_OPCODE_FIRMWARE_UPDATE_DATA_IND) + self.chunk_data
        )


@dataclass
class ForceBtDisconnectInd:
    """Force Bluetooth disconnect indication.

    Sent after firmware transfer to trigger device reboot.
    """

    restart_adv: bool = True  # Whether to restart advertising after disconnect

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return struct.pack(
            "<BB",
            TWIST_OPCODE_FORCE_BT_DISCONNECT_IND,
            1 if self.restart_adv else 0,
        )


# =============================================================================
# Flic 2 Firmware Update Messages (with frame header)
# =============================================================================


@dataclass
class Flic2StartFirmwareUpdateRequest:
    """Request to start a firmware update on a Flic 2 device.

    Flic 2 firmware binary has an 8-byte IV header followed by compressed data.
    The length field is in 32-bit words (not bytes).

    Format: [header:1][opcode:1][len_words:2][iv:8][status_interval:2]
    """

    connection_id: int
    length_compressed_words: int  # u16: length of compressed data in words
    iv: bytes  # 8 bytes
    status_interval: int = FLIC2_FIRMWARE_STATUS_INTERVAL  # u16

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        return (
            struct.pack(
                "<BBH",
                frame_header,
                OPCODE_START_FIRMWARE_UPDATE_REQUEST,
                self.length_compressed_words,
            )
            + self.iv
            + struct.pack("<H", self.status_interval)
        )

    @classmethod
    def from_firmware_binary(
        cls, firmware_binary: bytes, connection_id: int = 0
    ) -> Flic2StartFirmwareUpdateRequest:
        """Create request from a Flic 2 firmware binary file.

        Args:
            firmware_binary: Raw firmware binary (8-byte IV + compressed data)
            connection_id: Current connection ID

        """
        if len(firmware_binary) < FLIC2_FIRMWARE_IV_SIZE:
            raise ValueError(
                f"Firmware binary too short: {len(firmware_binary)} bytes "
                f"(minimum {FLIC2_FIRMWARE_IV_SIZE})"
            )

        iv = firmware_binary[:FLIC2_FIRMWARE_IV_SIZE]
        compressed_data = firmware_binary[FLIC2_FIRMWARE_IV_SIZE:]
        # Length in 32-bit words (truncate partial words to match reference)
        length_words = len(compressed_data) // 4

        return cls(
            connection_id=connection_id,
            length_compressed_words=length_words,
            iv=iv,
        )


@dataclass
class Flic2FirmwareUpdateDataInd:
    """Firmware data chunk sent to Flic 2 device during OTA update.

    Data is sent as 32-bit words. Format: [header:1][opcode:1][words[]:max 30 uint32]
    """

    connection_id: int
    words: list[int]  # List of uint32 values

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        payload = struct.pack("<BB", frame_header, OPCODE_FIRMWARE_UPDATE_DATA_IND)
        for word in self.words:
            payload += struct.pack("<I", word)
        return payload


@dataclass
class Flic2ForceBtDisconnectInd:
    """Force Bluetooth disconnect for Flic 2/Duo devices.

    Format: [header:1][opcode:1][restart_adv:1]
    """

    connection_id: int
    restart_adv: bool = True

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        return struct.pack(
            "<BBB",
            frame_header,
            OPCODE_FORCE_BT_DISCONNECT_IND,
            1 if self.restart_adv else 0,
        )


# =============================================================================
# Flic Duo Firmware Update Messages (with frame header)
# =============================================================================


@dataclass
class DuoStartFirmwareUpdateRequest:
    """Request to start a firmware update on a Flic Duo device.

    Duo uses the firmware3 API and has the same 76-byte header as Twist.
    Format: [header:1][opcode:1][len:4][header_76:76][status_interval:2]
    """

    connection_id: int
    length_compressed_bytes: int  # u32
    firmware_header: bytes  # 76 bytes (iv + uncompressed_words + signature)
    status_interval: int = DUO_FIRMWARE_STATUS_INTERVAL  # u16

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        return (
            struct.pack(
                "<BBI",
                frame_header,
                OPCODE_START_FIRMWARE_UPDATE_DUO_REQUEST,
                self.length_compressed_bytes,
            )
            + self.firmware_header
            + struct.pack("<H", self.status_interval)
        )

    @classmethod
    def from_firmware_binary(
        cls, firmware_binary: bytes, connection_id: int = 0
    ) -> DuoStartFirmwareUpdateRequest:
        """Create request from a Duo firmware binary file.

        Args:
            firmware_binary: Raw firmware binary (76-byte header + compressed data)
            connection_id: Current connection ID

        """
        if len(firmware_binary) < FIRMWARE_HEADER_SIZE:
            raise ValueError(
                f"Firmware binary too short: {len(firmware_binary)} bytes "
                f"(minimum {FIRMWARE_HEADER_SIZE})"
            )

        firmware_header = firmware_binary[:FIRMWARE_HEADER_SIZE]
        compressed_data = firmware_binary[FIRMWARE_HEADER_SIZE:]

        return cls(
            connection_id=connection_id,
            length_compressed_bytes=len(compressed_data),
            firmware_header=firmware_header,
        )


@dataclass
class DuoFirmwareUpdateDataInd:
    """Firmware data chunk sent to Duo device during OTA update.

    Format: [header:1][opcode:1][data[]:max 110 bytes]
    """

    connection_id: int
    chunk_data: bytes  # Up to DUO_FIRMWARE_DATA_CHUNK_SIZE bytes

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        frame_header = self.connection_id & 0x1F
        return (
            struct.pack("<BB", frame_header, OPCODE_FIRMWARE_UPDATE_DATA_DUO_IND)
            + self.chunk_data
        )
