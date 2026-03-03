"""Constants for the Keyboard Remote integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "keyboard_remote"

# Config entry data keys
CONF_DEVICE_PATH: Final = "device_path"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_DESCRIPTOR: Final = "device_descriptor"

# Options keys
CONF_KEY_TYPES: Final = "key_types"
CONF_EMULATE_KEY_HOLD: Final = "emulate_key_hold"
CONF_EMULATE_KEY_HOLD_DELAY: Final = "emulate_key_hold_delay"
CONF_EMULATE_KEY_HOLD_REPEAT: Final = "emulate_key_hold_repeat"

# Defaults
DEFAULT_KEY_TYPES: Final = ["key_up"]
DEFAULT_EMULATE_KEY_HOLD: Final = False
DEFAULT_EMULATE_KEY_HOLD_DELAY: Final = 0.250
DEFAULT_EMULATE_KEY_HOLD_REPEAT: Final = 0.033

# Key value mapping
KEY_VALUE: Final = {"key_up": 0, "key_down": 1, "key_hold": 2}
KEY_VALUE_NAME: Final = {value: key for key, value in KEY_VALUE.items()}

# Event names
EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED: Final = "keyboard_remote_command_received"
EVENT_KEYBOARD_REMOTE_CONNECTED: Final = "keyboard_remote_connected"
EVENT_KEYBOARD_REMOTE_DISCONNECTED: Final = "keyboard_remote_disconnected"

# Event data keys
KEY_CODE: Final = "key_code"

# System paths
DEVINPUT: Final = "/dev/input"
DEVINPUT_BY_ID: Final = "/dev/input/by-id"
