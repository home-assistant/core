"""Constants for Quantum Gateway."""

import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL
from homeassistant.helpers import config_validation as cv

LOGGER = logging.getLogger(__package__)

DEFAULT_HOST = "myfiosgateway.com"

DOMAIN = "quantum_gateway"
PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_SSL, default=True): cv.boolean,
        vol.Required(CONF_PASSWORD): cv.string,
    },
)

DATA_COODINATOR = "coordinator"
