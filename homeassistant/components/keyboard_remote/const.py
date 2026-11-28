"""Constants for the Keyboard Remote integration."""

from typing import Final

DOMAIN: Final = "keyboard_remote"

CONF_DEVICE_PATH: Final = "device_path"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_DESCRIPTOR: Final = "device_descriptor"
# The device's evdev uniq, a Bluetooth device's own address
CONF_DEVICE_UNIQ: Final = "device_uniq"

CONF_KEY_TYPES: Final = "key_types"
CONF_EMULATE_KEY_HOLD: Final = "emulate_key_hold"
CONF_EMULATE_KEY_HOLD_DELAY: Final = "emulate_key_hold_delay"
CONF_EMULATE_KEY_HOLD_REPEAT: Final = "emulate_key_hold_repeat"

DEFAULT_KEY_TYPES: Final = ["key_up"]
DEFAULT_EMULATE_KEY_HOLD: Final = False
DEFAULT_EMULATE_KEY_HOLD_DELAY: Final = 0.250
DEFAULT_EMULATE_KEY_HOLD_REPEAT: Final = 0.033

# Ranges the options form accepts, in seconds
EMULATE_KEY_HOLD_DELAY_MIN: Final = 0.01
EMULATE_KEY_HOLD_DELAY_MAX: Final = 5.0
EMULATE_KEY_HOLD_REPEAT_MIN: Final = 0.001
EMULATE_KEY_HOLD_REPEAT_MAX: Final = 1.0

KEY_VALUE: Final = {"key_up": 0, "key_down": 1, "key_hold": 2}
KEY_VALUE_NAME: Final = {value: key for key, value in KEY_VALUE.items()}

EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED: Final = "keyboard_remote_command_received"
EVENT_KEYBOARD_REMOTE_CONNECTED: Final = "keyboard_remote_connected"
EVENT_KEYBOARD_REMOTE_DISCONNECTED: Final = "keyboard_remote_disconnected"

KEY_CODE: Final = "key_code"

# Device match strength, lowest wins. A composite keyboard exposes several
# nodes reporting the same name, and only the one the user picked carries the
# configured by-id path, so a name match must never outrank a path match. A
# uniq match is a name match narrowed to one Bluetooth device.
MATCH_DEVICE_PATH: Final = 0
MATCH_DEVICE_UNIQ: Final = 1
MATCH_DEVICE_NAME: Final = 2

DEVINPUT: Final = "/dev/input"
DEVINPUT_BY_ID: Final = "/dev/input/by-id"
