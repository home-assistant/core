"""Constants for the Flic Button integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "flic_button"


class DeviceType(StrEnum):
    """Flic device types."""

    FLIC2 = "flic2"
    DUO = "duo"
    TWIST = "twist"

    @classmethod
    def from_serial_number(cls, serial: str) -> DeviceType:
        """Detect device type from serial number prefix."""
        if serial.startswith("T"):
            return cls.TWIST
        if serial.startswith("D"):
            return cls.DUO
        return cls.FLIC2


DEVICE_TYPE_MODEL_NAMES: Final = {
    DeviceType.FLIC2: "Flic 2",
    DeviceType.DUO: "Flic Duo",
    DeviceType.TWIST: "Flic Twist",
}

# Config entry data keys
CONF_PAIRING_ID: Final = "pairing_id"
CONF_PAIRING_KEY: Final = "pairing_key"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BATTERY_LEVEL: Final = "battery_level"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_SIG_BITS: Final = (
    "sig_bits"  # Ed25519 signature variant (0-3) for Twist quick verify
)

# Flic 2/Duo BLE Service and Characteristics
FLIC_SERVICE_UUID: Final = "00420000-8f59-4420-870d-84f3b617e493"
FLIC_WRITE_CHAR_UUID: Final = "00420001-8f59-4420-870d-84f3b617e493"
FLIC_NOTIFY_CHAR_UUID: Final = "00420002-8f59-4420-870d-84f3b617e493"

# Flic Twist BLE Service and Characteristics
TWIST_SERVICE_UUID: Final = "00c90000-2cbd-4f2a-a725-5ccd960ffb7d"
TWIST_TX_CHAR_UUID: Final = "00c90001-2cbd-4f2a-a725-5ccd960ffb7d"
TWIST_RX_CHAR_UUID: Final = "00c90002-2cbd-4f2a-a725-5ccd960ffb7d"

# Ed25519 public keys for signature verification
FLIC2_ED25519_PUBLIC_KEY: Final = bytes.fromhex(
    "d33f2440dd54b31b2e1dcf40132efa41d8f8a7474168df4008f5a95fb3b0d022"
)
TWIST_ED25519_PUBLIC_KEY: Final = bytes.fromhex(
    "a8b7df10434f565069e4131f5b13f1d9056faf2b61cf929b05d02d630bdaf48b"
)

# Protocol constants
FLIC_MTU: Final = 140  # Maximum ATT MTU
FLIC_MAX_PACKET_SIZE: Final = 129  # Maximum packet size (140 - 11 ATT overhead)
FLIC_SIGNATURE_SIZE: Final = 5  # Chaskey-LTS MAC size for packets

# Frame header bitmasks (Flic 2/Duo framing)
FRAME_HEADER_CONN_ID_MASK: Final = 0x1F
FRAME_HEADER_NEWLY_ASSIGNED: Final = 0x20
FRAME_HEADER_FRAGMENT_FLAG: Final = 0x80

# Event types
EVENT_TYPE_UP: Final = "up"
EVENT_TYPE_DOWN: Final = "down"
EVENT_TYPE_CLICK: Final = "click"
EVENT_TYPE_DOUBLE_CLICK: Final = "double_click"
EVENT_TYPE_HOLD: Final = "hold"

# Gesture event types (Flic Duo only)
EVENT_TYPE_SWIPE_LEFT: Final = "swipe_left"
EVENT_TYPE_SWIPE_RIGHT: Final = "swipe_right"
EVENT_TYPE_SWIPE_UP: Final = "swipe_up"
EVENT_TYPE_SWIPE_DOWN: Final = "swipe_down"

# Rotate event types (Flic Duo and Twist)
EVENT_TYPE_ROTATE_CLOCKWISE: Final = "rotate_clockwise"
EVENT_TYPE_ROTATE_COUNTER_CLOCKWISE: Final = "rotate_counter_clockwise"

# Twist-specific event types
EVENT_TYPE_SELECTOR_CHANGED: Final = "selector_changed"

# Twist DEFAULT mode increment/decrement event types
EVENT_TYPE_TWIST_INCREMENT: Final = "twist_increment"
EVENT_TYPE_TWIST_DECREMENT: Final = "twist_decrement"
EVENT_TYPE_PUSH_TWIST_INCREMENT: Final = "push_twist_increment"
EVENT_TYPE_PUSH_TWIST_DECREMENT: Final = "push_twist_decrement"

# Twist slot position changed event types (one per slot, modes 0-11)
EVENT_TYPE_SLOT_CHANGED: Final = [f"slot_{i}_changed" for i in range(1, 13)]

# Duo dial position changed event type
EVENT_TYPE_DUO_DIAL_CHANGED: Final = "duo_dial_changed"

# Event classes
EVENT_CLASS_BUTTON: Final = "button"

# Flic event domain
FLIC_BUTTON_EVENT: Final = f"{DOMAIN}_event"
FLIC_ROTATE_EVENT: Final = f"{DOMAIN}_rotate_event"

# Timeouts (seconds)
PAIRING_TIMEOUT: Final = 60
CONNECTION_TIMEOUT: Final = 30
COMMAND_TIMEOUT: Final = 10

# BLE connection parameters
# These are requested after establishing the BLE connection
CONN_PARAM_LATENCY: Final = 17  # Slave latency (connection events peripheral can skip)
CONN_PARAM_INTERVAL_MIN: Final = 80  # Min interval (units of 1.25ms = 100ms)
CONN_PARAM_INTERVAL_MAX: Final = 90  # Max interval (units of 1.25ms = 112.5ms)
CONN_PARAM_TIMEOUT: Final = 800  # Supervision timeout (units of 10ms = 8000ms)

# Protocol opcodes - from official Flic 2 SDK
# Request opcodes (OpcodeToFlic)
OPCODE_FULL_VERIFY_REQUEST_1: Final = 0
OPCODE_FULL_VERIFY_REQUEST_2: Final = 2  # FULL_VERIFY_REQUEST_2_WITHOUT_APP_TOKEN
OPCODE_QUICK_VERIFY_REQUEST: Final = 5
OPCODE_GET_FIRMWARE_VERSION_REQUEST: Final = 8
OPCODE_GET_BATTERY_LEVEL_REQUEST: Final = 20
OPCODE_INIT_BUTTON_EVENTS_REQUEST: Final = 23  # INIT_BUTTON_EVENTS_LIGHT_REQUEST

# Response opcodes (OpcodeFromFlic)
OPCODE_FULL_VERIFY_RESPONSE_1: Final = 0
OPCODE_FULL_VERIFY_RESPONSE_2: Final = 1
OPCODE_GET_FIRMWARE_VERSION_RESPONSE: Final = 5
OPCODE_QUICK_VERIFY_RESPONSE: Final = 8
OPCODE_BUTTON_EVENT: Final = 12  # BUTTON_EVENT_NOTIFICATION
OPCODE_GET_BATTERY_LEVEL_RESPONSE: Final = 20

# Button event types for Flic 2 (non-Duo) from SDK ButtonEventNotificationItem
# These are encoded in 4 bits with extended types for UP events
# Format: timestamp(48 bits) + eventEncoded(4 bits) + wasQueued(1) + wasQueuedLast(1) + padding(2)
# Basic events (0-3):
FLIC2_EVENT_UP: Final = 0  # Button released (simple, no click context)
FLIC2_EVENT_DOWN: Final = 1  # Button pressed
FLIC2_EVENT_SINGLE_CLICK_TIMEOUT: Final = 2  # Single click confirmed (timeout expired)
FLIC2_EVENT_HOLD: Final = 3  # Button held down
# Extended UP events (8-15) - these indicate button release with additional context:
FLIC2_EVENT_UP_CLICK_PENDING: Final = 8  # Button released, click detection in progress
FLIC2_EVENT_UP_SINGLE_CLICK: Final = 10  # Button released, single click detected
FLIC2_EVENT_UP_DOUBLE_CLICK: Final = 11  # Button released, double click detected
FLIC2_EVENT_UP_AFTER_HOLD: Final = 14  # Button released after hold

# Response opcodes for button event initialization
OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITH_BOOT_ID: Final = 10
OPCODE_INIT_BUTTON_EVENTS_RESPONSE_WITHOUT_BOOT_ID: Final = 11

# Flic Duo specific opcodes (from SDK Opcodes.kt)
OPCODE_INIT_BUTTON_EVENTS_DUO_REQUEST: Final = (
    35  # INIT_BUTTON_EVENTS_DUO_LIGHT_REQUEST
)
OPCODE_BUTTON_EVENT_DUO: Final = 32  # BUTTON_EVENT_DUO_NOTIFICATION
OPCODE_ENABLE_PUSH_TWIST_IND: Final = 37  # Enable push twist (rotation) events
OPCODE_PUSH_TWIST_DATA_NOTIFICATION: Final = 33  # Push twist data notification

# Response opcodes for Duo button event initialization
OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITH_BOOT_ID: Final = 30
OPCODE_INIT_BUTTON_EVENTS_DUO_RESPONSE_WITHOUT_BOOT_ID: Final = 31

# ============================================================================
# Flic Twist specific opcodes (simpler packet framing than Flic 2/Duo)
# ============================================================================

# Twist opcodes (Host → Device)
TWIST_OPCODE_FULL_VERIFY_REQUEST_1: Final = 0x00
TWIST_OPCODE_FULL_VERIFY_REQUEST_2: Final = 0x02  # Without app token
TWIST_OPCODE_QUICK_VERIFY_REQUEST: Final = 0x05
TWIST_OPCODE_INIT_BUTTON_EVENTS: Final = 0x0C  # 12, with 13 config items
TWIST_OPCODE_ACK_BUTTON_EVENTS: Final = 0x0D  # 13
TWIST_OPCODE_UPDATE_TWIST_POS: Final = 0x0E  # 14
TWIST_OPCODE_GET_FIRMWARE_VERSION_REQUEST: Final = 0x07
TWIST_OPCODE_GET_BATTERY_LEVEL_REQUEST: Final = 0x11  # 17

# Twist opcodes (Device → Host)
TWIST_OPCODE_FULL_VERIFY_RESPONSE_1: Final = 0x00
TWIST_OPCODE_FULL_VERIFY_RESPONSE_2: Final = 0x01
TWIST_OPCODE_FULL_VERIFY_FAIL_RESPONSE: Final = 0x02  # Failure with reason
TWIST_OPCODE_GET_FIRMWARE_VERSION_RESPONSE: Final = 0x04
TWIST_OPCODE_QUICK_VERIFY_NEGATIVE: Final = 0x05
TWIST_OPCODE_QUICK_VERIFY_RESPONSE: Final = 0x06
TWIST_OPCODE_DISCONNECTED_VERIFIED_LINK: Final = 0x07  # Disconnect with reason
TWIST_OPCODE_INIT_BUTTON_EVENTS_RESPONSE: Final = 0x08
TWIST_OPCODE_BUTTON_EVENT: Final = 0x09  # 9
TWIST_OPCODE_TWIST_EVENT: Final = 0x0A  # 10
TWIST_OPCODE_GET_BATTERY_LEVEL_RESPONSE: Final = 0x10  # 16

# Twist disconnect reasons
TWIST_DISCONNECT_REASON_INVALID_SIGNATURE: Final = 0
TWIST_DISCONNECT_REASON_OTHER_CLIENT: Final = 1

# Twist mode indices
TWIST_MODE_SLOT_FIRST: Final = 0  # First slot (Slot 1)
TWIST_MODE_SLOT_LAST: Final = 11  # Last slot (Slot 12)
TWIST_MODE_SLOT_CHANGING: Final = 12  # Slot-changing mode (selecting active slot)

# Options constants
CONF_PUSH_TWIST_MODE: Final = "push_twist_mode"


class PushTwistMode(StrEnum):
    """Push twist mode options."""

    DEFAULT = "default"
    CONTINUOUS = "continuous"
    SELECTOR = "selector"


# ============================================================================
# Firmware update constants
# ============================================================================

# Twist firmware update opcodes (Host -> Device)
TWIST_OPCODE_FORCE_BT_DISCONNECT_IND: Final = 0x06
TWIST_OPCODE_START_FIRMWARE_UPDATE_REQUEST: Final = 0x0F
TWIST_OPCODE_FIRMWARE_UPDATE_DATA_IND: Final = 0x10

# Twist firmware update opcodes (Device -> Host)
TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE: Final = 0x0E
TWIST_OPCODE_FIRMWARE_UPDATE_NOTIFICATION: Final = 0x0F

# Flic 2 firmware update opcodes (Host -> Device, with frame header)
OPCODE_FORCE_BT_DISCONNECT_IND: Final = 6
OPCODE_START_FIRMWARE_UPDATE_REQUEST: Final = 17
OPCODE_FIRMWARE_UPDATE_DATA_IND: Final = 18

# Flic 2 firmware update opcodes (Device -> Host, with frame header)
OPCODE_START_FIRMWARE_UPDATE_RESPONSE: Final = 18
OPCODE_FIRMWARE_UPDATE_NOTIFICATION: Final = 19

# Flic Duo firmware update opcodes (Host -> Device, with frame header)
OPCODE_START_FIRMWARE_UPDATE_DUO_REQUEST: Final = 38
OPCODE_FIRMWARE_UPDATE_DATA_DUO_IND: Final = 39

# Firmware binary header
FIRMWARE_HEADER_SIZE: Final = 76

# Twist transfer constants
FIRMWARE_DATA_CHUNK_SIZE: Final = 120  # Max payload bytes per data packet
FIRMWARE_MAX_IN_FLIGHT: Final = 480  # Max unacknowledged bytes (4 * 120)
FIRMWARE_STATUS_INTERVAL: Final = 2  # Device reports progress every N packets
FIRMWARE_UPDATE_TIMEOUT: Final = 300  # 5 min timeout for firmware transfer
FIRMWARE_FINAL_ACK_TIMEOUT: Final = (
    30  # Shorter timeout for final ACK after all data sent
)

# Flic 2 transfer constants (word-based: 1 word = 4 bytes)
FLIC2_FIRMWARE_WORD_CHUNK_SIZE: Final = 30  # Max words per data packet
FLIC2_FIRMWARE_MAX_IN_FLIGHT_WORDS: Final = 512  # Max unacknowledged words
FLIC2_FIRMWARE_STATUS_INTERVAL: Final = 60  # Device reports progress every N packets
FLIC2_FIRMWARE_IV_SIZE: Final = 8  # IV size in firmware header for Flic 2

# Duo transfer constants (byte-based like Twist but different sizes)
DUO_FIRMWARE_DATA_CHUNK_SIZE: Final = 110  # Max payload bytes per data packet
DUO_FIRMWARE_MAX_IN_FLIGHT: Final = 550  # Max unacknowledged bytes
DUO_FIRMWARE_STATUS_INTERVAL: Final = 2  # Device reports progress every N packets

# Flic firmware APIs
FLIC_FIRMWARE_API_URL: Final = "https://api.flic.io/api/v1/buttons/versions/firmware2"
FLIC_FIRMWARE3_API_URL: Final = "https://api.flic.io/api/v1/buttons/versions/firmware3"

# Name management opcodes - Flic 2/Duo (Host -> Device)
OPCODE_SET_NAME_REQUEST: Final = 10
OPCODE_GET_NAME_REQUEST: Final = 11

# Name management opcodes - Flic 2/Duo (Device -> Host)
OPCODE_GET_NAME_RESPONSE: Final = 16
OPCODE_SET_NAME_RESPONSE: Final = 17

# Name management opcodes - Twist (Host -> Device)
TWIST_OPCODE_SET_NAME_REQUEST: Final = 0x09
TWIST_OPCODE_GET_NAME_REQUEST: Final = 0x0A

# Name management opcodes - Twist (Device -> Host)
TWIST_OPCODE_GET_NAME_RESPONSE: Final = 0x0C
TWIST_OPCODE_SET_NAME_RESPONSE: Final = 0x0D

# Name constraints
DEVICE_NAME_MAX_BYTES: Final = 23

# Config entry key for button UUID
CONF_BUTTON_UUID: Final = "button_uuid"
