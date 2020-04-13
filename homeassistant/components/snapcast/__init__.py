"""The snapcast component."""

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv

DOMAIN = "snapcast"

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
SERVICE_SET_LATENCY = "set_latency"

ATTR_MASTER = "master"
ATTR_LATENCY = "latency"

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})

JOIN_SERVICE_SCHEMA = SERVICE_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})

LATENCY_SCHEMA = SERVICE_SCHEMA.extend({vol.Required(ATTR_LATENCY): cv.positive_int})
