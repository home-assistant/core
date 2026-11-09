"""Constants for the script integration."""

from enum import StrEnum
import logging

DOMAIN = "script"

ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_VARIABLES = "variables"

CONF_ADVANCED = "advanced"
CONF_EXAMPLE = "example"
CONF_FIELDS = "fields"
CONF_REQUIRED = "required"
CONF_TRACE = "trace"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

EVENT_SCRIPT_STARTED = "script_started"

LOGGER = logging.getLogger(__package__)


class ScriptEntityStateAttribute(StrEnum):
    """State attributes for script entities."""

    LAST_TRIGGERED = "last_triggered"
    MODE = "mode"
    CURRENT = "current"
    MAX = "max"
    LAST_ACTION = "last_action"


class ScriptService(StrEnum):
    """Store keys for script services."""

    RELOAD = "reload"
    TOGGLE = "toggle"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"
