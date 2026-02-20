"""Base protocol handler for Flic devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from ..const import (
    EVENT_TYPE_CLICK,
    EVENT_TYPE_DOUBLE_CLICK,
    EVENT_TYPE_DOWN,
    EVENT_TYPE_HOLD,
    EVENT_TYPE_UP,
    FLIC2_EVENT_DOWN,
    FLIC2_EVENT_HOLD,
    FLIC2_EVENT_SINGLE_CLICK_TIMEOUT,
    FLIC2_EVENT_UP,
    FLIC2_EVENT_UP_AFTER_HOLD,
    FLIC2_EVENT_UP_CLICK_PENDING,
    FLIC2_EVENT_UP_DOUBLE_CLICK,
    FLIC2_EVENT_UP_SINGLE_CLICK,
)

if TYPE_CHECKING:
    from ..rotate_tracker import RotateTracker

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceCapabilities:
    """Capabilities of a Flic device.

    This dataclass describes what features a device supports,
    enabling capability-based entity and trigger creation.
    """

    button_count: int  # 1 for Flic2/Twist, 2 for Duo
    has_rotation: bool  # True for Duo/Twist
    has_selector: bool  # True for Twist only (modes 1-11)
    has_gestures: bool  # True for Duo only (swipe gestures)
    has_frame_header: bool  # True for Flic2/Duo, False for Twist


@dataclass
class ButtonEvent:
    """Button event data."""

    event_type: str
    button_index: int | None  # None for single-button devices
    timestamp_ms: int
    was_queued: bool
    extra_data: dict[str, Any]


@dataclass
class RotateEvent:
    """Rotation event data."""

    event_type: str  # rotate_clockwise or rotate_counter_clockwise
    button_index: int | None  # Which button was pressed (Duo) or None (Twist)
    angle_degrees: float
    detent_crossings: int
    extra_data: dict[str, Any]


# Type aliases for callback functions passed to handlers
WritePacketFn = Callable[[bytes, bool], Awaitable[None]]
WaitForOpcodesFn = Callable[[list[int]], Awaitable[bytes]]
WaitForOpcodeFn = Callable[[int], Awaitable[bytes]]
WriteGattFn = Callable[[str, bytes], Awaitable[None]]


class DeviceProtocolHandler(ABC):
    """Abstract base class for device-specific protocol handlers.

    Each device type (Flic 2, Duo, Twist) implements this interface
    to handle its specific pairing, authentication, and event protocols.
    """

    def __init__(self) -> None:
        """Initialize the handler."""
        self._rotate_tracker: RotateTracker | None = None

    @property
    @abstractmethod
    def service_uuid(self) -> str:
        """Return the BLE service UUID for this device type."""

    @property
    @abstractmethod
    def write_char_uuid(self) -> str:
        """Return the BLE write characteristic UUID."""

    @property
    @abstractmethod
    def notify_char_uuid(self) -> str:
        """Return the BLE notify characteristic UUID."""

    @property
    @abstractmethod
    def ed25519_public_key(self) -> bytes:
        """Return the Ed25519 public key for signature verification."""

    @property
    @abstractmethod
    def capabilities(self) -> DeviceCapabilities:
        """Return the device capabilities."""

    @abstractmethod
    async def full_verify_pairing(
        self,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> tuple[int, bytes, str, int] | tuple[int, bytes, str, int, int]:
        """Perform full pairing verification.

        Args:
            write_gatt: Function to write to GATT characteristic
            wait_for_opcode: Function to wait for a specific opcode
            wait_for_opcodes: Function to wait for one of multiple opcodes
            write_packet: Function to write authenticated packets

        Returns:
            Tuple of (pairing_id, pairing_key, serial_number, battery_level)
            or (pairing_id, pairing_key, serial_number, battery_level, sig_bits)

        """

    @abstractmethod
    async def quick_verify(
        self,
        pairing_id: int,
        pairing_key: bytes,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        write_packet: WritePacketFn,
        sig_bits: int = 0,
    ) -> tuple[bytes, list[int]]:
        """Perform quick verification using stored credentials.

        Args:
            pairing_id: Stored pairing ID
            pairing_key: Stored pairing key
            write_gatt: Function to write to GATT characteristic
            wait_for_opcode: Function to wait for a specific opcode
            write_packet: Function to write packets
            sig_bits: Ed25519 signature variant (0-3), used by Twist

        Returns:
            Tuple of (session_key, chaskey_subkeys)

        """

    @abstractmethod
    async def init_button_events(
        self,
        connection_id: int,
        session_key: bytes | None,
        chaskey_keys: list[int] | None,
        write_gatt: WriteGattFn,
        wait_for_opcode: WaitForOpcodeFn,
        wait_for_opcodes: WaitForOpcodesFn,
        write_packet: WritePacketFn,
    ) -> None:
        """Initialize button event delivery.

        Args:
            connection_id: Current connection ID
            session_key: Session key (for authenticated packets)
            chaskey_keys: Chaskey subkeys for MAC
            write_gatt: Function to write to GATT characteristic
            wait_for_opcode: Function to wait for a specific opcode
            wait_for_opcodes: Function to wait for one of multiple opcodes
            write_packet: Function to write authenticated packets

        """

    @abstractmethod
    async def get_firmware_version(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the firmware version from the device.

        Args:
            connection_id: Current connection ID
            write_packet: Function to write authenticated packets
            wait_for_opcode: Function to wait for a specific opcode

        Returns:
            Firmware version as an integer

        """

    @abstractmethod
    def handle_notification(
        self,
        data: bytes,
        connection_id: int,
    ) -> tuple[list[ButtonEvent], list[RotateEvent], int | None]:
        """Handle a notification from the device.

        This processes event notifications and returns parsed events.
        This method does NOT handle MAC verification - that's done by FlicClient.

        Args:
            data: Raw notification data (after MAC verification if applicable)
            connection_id: Current connection ID

        Returns:
            Tuple of (button_events, rotate_events, new_selector_index or None)

        """

    def reset_state(self) -> None:
        """Reset any handler-specific state (called on disconnect)."""
        self._rotate_tracker = None

    def _get_event_name(self, event_type: int) -> str:
        """Get human-readable name for event type."""
        names = {
            FLIC2_EVENT_UP: "UP_SIMPLE",
            FLIC2_EVENT_DOWN: "DOWN",
            FLIC2_EVENT_SINGLE_CLICK_TIMEOUT: "CLICK",
            FLIC2_EVENT_HOLD: "HOLD",
            FLIC2_EVENT_UP_CLICK_PENDING: "UP_CLICK_PENDING",
            FLIC2_EVENT_UP_SINGLE_CLICK: "UP_SINGLE_CLICK",
            FLIC2_EVENT_UP_DOUBLE_CLICK: "UP_DOUBLE_CLICK",
            FLIC2_EVENT_UP_AFTER_HOLD: "UP_AFTER_HOLD",
        }
        return names.get(event_type, f"UNKNOWN({event_type})")

    def _map_event_type(self, event_type: int) -> str | None:
        """Map event type to Home Assistant event type."""
        if event_type == FLIC2_EVENT_UP:
            return EVENT_TYPE_UP
        if event_type == FLIC2_EVENT_DOWN:
            return EVENT_TYPE_DOWN
        if event_type == FLIC2_EVENT_SINGLE_CLICK_TIMEOUT:
            return EVENT_TYPE_CLICK
        if event_type == FLIC2_EVENT_HOLD:
            return EVENT_TYPE_HOLD
        if event_type == FLIC2_EVENT_UP_CLICK_PENDING:
            return EVENT_TYPE_UP
        if event_type == FLIC2_EVENT_UP_SINGLE_CLICK:
            return EVENT_TYPE_UP
        if event_type == FLIC2_EVENT_UP_DOUBLE_CLICK:
            return EVENT_TYPE_DOUBLE_CLICK
        if event_type == FLIC2_EVENT_UP_AFTER_HOLD:
            return EVENT_TYPE_UP

        _LOGGER.debug("Unknown button event type: %d", event_type)
        return None
