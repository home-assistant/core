"""Const for PJLink."""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

INTEGRATION_NAME = "PJLink"
DOMAIN = "pjlink"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_ENCODING = "encoding"
CONF_PASSWORD = "password"

DEFAULT_PORT = 4352
DEFAULT_ENCODING = "utf-8"
DEFAULT_TIMEOUT = 10

UPDATE_INTERVAL = 10

ERROR_KEYS = [
    ("fan", "Fan Error"),
    ("lamp", "Lamp Error"),
    ("temp", "Temperature Error"),
    ("cover", "Cover Error"),
    ("filter", "Filter Error"),
    ("other", "Other Error"),
]

ATTR_IS_WARNING = "is_warning"
ATTR_PROJECTOR_STATUS = "projector_status"
ATTR_OTHER_INFO = "other_info"

ATTR_TO_PROPERTY = [
    ATTR_PROJECTOR_STATUS,
    ATTR_OTHER_INFO,
]

CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=""): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
    }
)

_LOGGER = logging.getLogger(__package__)
