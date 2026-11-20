"""Constants for the automation integration."""

from enum import StrEnum
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .entity import BaseAutomationEntity

CONF_TRIGGER_VARIABLES = "trigger_variables"
DOMAIN = "automation"

ATTR_SOURCE = "source"
EVENT_AUTOMATION_RELOADED = "automation_reloaded"
EVENT_AUTOMATION_TRIGGERED = "automation_triggered"

DATA_COMPONENT: HassKey[EntityComponent[BaseAutomationEntity]] = HassKey(DOMAIN)

DEFAULT_STOP_ACTIONS = True


class AutomationService(StrEnum):
    """Store keys for automation services."""

    RELOAD = "reload"
    TOGGLE = "toggle"
    TRIGGER = "trigger"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"


class AutomationServiceArgument(StrEnum):
    """Store keys for automation service arguments."""

    SKIP_CONDITION = "skip_condition"
    STOP_ACTIONS = "stop_actions"
    VARIABLES = "variables"


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
