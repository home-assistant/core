"""Constants for the Shelly Button Manager integration."""
from enum import StrEnum
from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

DOMAIN: Final = "shelly_button_manager"
TARGET_DOMAIN: Final = "shelly"

TARGET_STATE_ATTR_NAME: Final = "set_state"
TARGET_STATE_ATTR_DEFAULT_VALUE: Final = "Toggle"
ALL_DEVICES_ATTR_NAME: Final = "all_devices"
ALL_DEVICES_ATTR_DEFAULT_VALUE: Final = False

DATA_CONFIG_ENTRY: Final = "config_entry"


class ButtonType(StrEnum):
    """The possible states of a button."""

    Toggle = "toggle"
    Momentary = "momentary"
    Edge = "edge"
    Detached = "detached"
