"""Constants for the INELNET Blinds integration."""

from inelnet_api import Action

DOMAIN = "inelnet"

CONF_CHANNELS = "channels"

# Device action types for device_action.py (string keys)
ACTION_UP_SHORT = "up_short"
ACTION_DOWN_SHORT = "down_short"
ACTION_PROGRAM = "program"

__all__ = [
    "ACTION_DOWN_SHORT",
    "ACTION_PROGRAM",
    "ACTION_UP_SHORT",
    "CONF_CHANNELS",
    "DOMAIN",
    "Action",
]
