"""Common code for TCP component."""

from typing import Any, Final

import probatio

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BUFFER_SIZE,
    CONF_VALUE_ON,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
)

TCP_PLATFORM_SCHEMA: Final[dict[probatio.Marker, Any]] = {
    probatio.Required(CONF_HOST): cv.string,
    probatio.Required(CONF_PORT): cv.port,
    probatio.Required(CONF_PAYLOAD): cv.string,
    probatio.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
    probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    probatio.Optional(CONF_VALUE_ON): cv.string,
    probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
    probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
}
