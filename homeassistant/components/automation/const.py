"""Constants for the automation integration."""
import logging

CONF_ACTION = "action"
CONF_TRIGGER = "trigger"
CONF_TRIGGER_VARIABLES = "trigger_variables"
DOMAIN = "automation"

CONF_DESCRIPTION = "description"
CONF_HIDE_ENTITY = "hide_entity"

CONF_CONDITION_TYPE = "condition_type"
CONF_INITIAL_STATE = "initial_state"
CONF_BLUEPRINT = "blueprint"
CONF_INPUT = "input"

DEFAULT_INITIAL_STATE = True

LOGGER = logging.getLogger(__package__)
