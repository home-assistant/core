"""Constants for the script integration."""

import logging

DOMAIN = "script"

ATTR_LAST_ACTION = "last_action"
ATTR_LAST_TRIGGERED = "last_triggered"
ATTR_VARIABLES = "variables"
ATTR_WAIT_FOR_START = "wait_for_start"

CONF_ADVANCED = "advanced"
CONF_EXAMPLE = "example"
CONF_FIELDS = "fields"
CONF_REQUIRED = "required"
CONF_TRACE = "trace"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

EVENT_SCRIPT_STARTED = "script_started"

LOGGER = logging.getLogger(__package__)
