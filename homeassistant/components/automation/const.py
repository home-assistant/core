"""Constants for the automation integration."""

from enum import StrEnum
import logging

CONF_TRIGGER_VARIABLES = "trigger_variables"
DOMAIN = "automation"


class AutomationEntityCapabilityAttribute(StrEnum):
    """Capability attributes for automation entities."""

    ID = "id"


class AutomationEntityStateAttribute(StrEnum):
    """State attributes for automation entities."""

    LAST_TRIGGERED = "last_triggered"
    MODE = "mode"
    CUR = "current"
    MAX = "max"


CONF_HIDE_ENTITY = "hide_entity"

CONF_CONDITION_TYPE = "condition_type"
CONF_INITIAL_STATE = "initial_state"
CONF_BLUEPRINT = "blueprint"
CONF_INPUT = "input"
CONF_TRACE = "trace"

DEFAULT_INITIAL_STATE = True

LOGGER = logging.getLogger(__package__)
