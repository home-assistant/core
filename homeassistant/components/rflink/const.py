"""Support for Rflink devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

CONF_ALIASES = "aliases"
CONF_GROUP_ALIASES = "group_aliases"
CONF_GROUP = "group"
CONF_NOGROUP_ALIASES = "nogroup_aliases"
CONF_DEVICE_DEFAULTS = "device_defaults"
CONF_AUTOMATIC_ADD = "automatic_add"
CONF_FIRE_EVENT = "fire_event"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"

DATA_DEVICE_REGISTER = "rflink_device_register"
DATA_ENTITY_GROUP_LOOKUP = "rflink_entity_group_only_lookup"
DATA_ENTITY_LOOKUP = "rflink_entity_lookup"
DEFAULT_SIGNAL_REPETITIONS = 1

EVENT_KEY_COMMAND = "command"
EVENT_KEY_ID = "id"
EVENT_KEY_SENSOR = "sensor"
EVENT_KEY_UNIT = "unit"

SIGNAL_AVAILABILITY = "rflink_device_available"
SIGNAL_HANDLE_EVENT = "rflink_handle_event_{}"

TMP_ENTITY = "tmp.{}"

DEVICE_DEFAULTS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
        vol.Optional(
            CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS
        ): vol.Coerce(int),
    }
)
