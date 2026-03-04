"""Base protocol handler for Flic devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from ..const import (
    DEVICE_NAME_MAX_BYTES,
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
    """Abstract base class for device-specific protocol handlers."""

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
    ) -> tuple[int, bytes, str, int, int, bytes, int]:
        """Perform full pairing verification."""

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
        """Perform quick verification using stored credentials."""

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
        """Initialize button event delivery."""

    @abstractmethod
    async def get_battery_level(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the battery level from the device."""

    @abstractmethod
    async def get_firmware_version(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> int:
        """Request and return the firmware version from the device."""

    @abstractmethod
    def handle_notification(
        self,
        data: bytes,
        connection_id: int,
    ) -> tuple[list[ButtonEvent], list[RotateEvent], int | None]:
        """Handle a notification from the device."""

    @abstractmethod
    async def start_firmware_update(
        self,
        firmware_binary: bytes,
        write_packet: WritePacketFn,
        wait_for_opcodes: WaitForOpcodesFn,
    ) -> int:
        """Start a firmware update on the device."""

    @abstractmethod
    async def send_firmware_data(
        self,
        firmware_binary: bytes,
        start_pos: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Send firmware data chunks to the device."""

    @abstractmethod
    async def send_force_disconnect(
        self,
        write_packet: WritePacketFn,
        restart_adv: bool = True,
    ) -> None:
        """Send force disconnect to trigger device reboot."""

    @abstractmethod
    async def get_name(
        self,
        connection_id: int,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> tuple[str, int]:
        """Request and return the device name."""

    @abstractmethod
    async def set_name(
        self,
        connection_id: int,
        name: str,
        write_packet: WritePacketFn,
        wait_for_opcode: WaitForOpcodeFn,
    ) -> tuple[str, int]:
        """Set the device name."""

    def reset_state(self) -> None:
        """Reset any handler-specific state (called on disconnect)."""
        self._rotate_tracker = None

    @staticmethod
    def _truncate_name_bytes(name: str) -> bytes:
        """Truncate a name to fit within DEVICE_NAME_MAX_BYTES UTF-8 bytes."""
        encoded = name.encode("utf-8")
        if len(encoded) <= DEVICE_NAME_MAX_BYTES:
            return encoded
        # Truncate and decode with error handling to ensure valid boundary
        return (
            encoded[:DEVICE_NAME_MAX_BYTES]
            .decode("utf-8", errors="ignore")
            .encode("utf-8")
        )

    @staticmethod
    def _validate_firmware_start_pos(start_pos: int) -> int:
        """Validate firmware update start position, raising on error codes."""
        if start_pos == -1:
            raise ValueError("Device rejected firmware update: invalid parameters")
        if start_pos == -2:
            raise ValueError("Device rejected firmware update: device busy")
        if start_pos == -3:
            raise ValueError(
                "Device rejected firmware update: pending reboot from previous update"
            )
        if start_pos < 0:
            raise ValueError(
                f"Device rejected firmware update: unknown error code {start_pos}"
            )
        return start_pos

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

    _EVENT_TYPE_MAP: dict[int, str] = {
        FLIC2_EVENT_UP: EVENT_TYPE_UP,
        FLIC2_EVENT_UP_CLICK_PENDING: EVENT_TYPE_UP,
        FLIC2_EVENT_UP_SINGLE_CLICK: EVENT_TYPE_UP,
        FLIC2_EVENT_UP_AFTER_HOLD: EVENT_TYPE_UP,
        FLIC2_EVENT_DOWN: EVENT_TYPE_DOWN,
        FLIC2_EVENT_SINGLE_CLICK_TIMEOUT: EVENT_TYPE_CLICK,
        FLIC2_EVENT_HOLD: EVENT_TYPE_HOLD,
        FLIC2_EVENT_UP_DOUBLE_CLICK: EVENT_TYPE_DOUBLE_CLICK,
    }

    def _map_event_type(self, event_type: int) -> str | None:
        """Map event type to Home Assistant event type."""
        mapped = self._EVENT_TYPE_MAP.get(event_type)
        if mapped is None:
            _LOGGER.debug("Unknown button event type: %d", event_type)
        return mapped
