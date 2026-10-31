"""Constants for the remote component."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import RemoteEntity

DOMAIN: Final = "remote"
DATA_COMPONENT: HassKey[EntityComponent[RemoteEntity]] = HassKey(DOMAIN)

ATTR_ACTIVITY = "activity"
ATTR_ACTIVITY_LIST = "activity_list"
ATTR_CURRENT_ACTIVITY = "current_activity"
ATTR_COMMAND_TYPE = "command_type"
ATTR_DEVICE = "device"
ATTR_NUM_REPEATS = "num_repeats"
ATTR_DELAY_SECS = "delay_secs"
ATTR_HOLD_SECS = "hold_secs"
ATTR_ALTERNATIVE = "alternative"
ATTR_TIMEOUT = "timeout"

SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_DELETE_COMMAND = "delete_command"
SERVICE_SYNC = "sync"

DEFAULT_NUM_REPEATS = 1
DEFAULT_DELAY_SECS = 0.4
DEFAULT_HOLD_SECS = 0


class RemoteEntityStateAttribute(StrEnum):
    """State attributes for remote entities."""

    ACTIVITY_LIST = "activity_list"
    CURRENT_ACTIVITY = "current_activity"


class RemoteEntityCapabilityAttribute(StrEnum):
    """Capability attributes for remote entities."""

    SUPPORTED_NAVIGATION = "supported_navigation"


class RemoteNavigation(StrEnum):
    """Standard navigation (d-pad) actions of a remote."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SELECT = "select"
    BACK = "back"
    HOME = "home"
    MENU = "menu"


class RemoteEntityFeature(IntFlag):
    """Supported features of the remote entity."""

    LEARN_COMMAND = 1
    DELETE_COMMAND = 2
    ACTIVITY = 4
    NAVIGATE = 8


class RemoteService(StrEnum):
    """Store keys for remote services."""

    DELETE_COMMAND = "delete_command"
    LEARN_COMMAND = "learn_command"
    NAVIGATE = "navigate"
    SEND_COMMAND = "send_command"
    TOGGLE = "toggle"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"


class RemoteServiceArgument(StrEnum):
    """Store keys for remote service arguments."""

    ACTIVITY = "activity"
    ALTERNATIVE = "alternative"
    COMMAND = "command"
    COMMAND_TYPE = "command_type"
    DELAY_SECS = "delay_secs"
    DEVICE = "device"
    DIRECTION = "direction"
    HOLD_SECS = "hold_secs"
    NUM_REPEATS = "num_repeats"
    TIMEOUT = "timeout"
