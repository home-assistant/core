"""The command_line component."""

import logging

import probatio

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    SCAN_INTERVAL as BINARY_SENSOR_DEFAULT_SCAN_INTERVAL,
)
from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
    DOMAIN as COVER_DOMAIN,
    SCAN_INTERVAL as COVER_DEFAULT_SCAN_INTERVAL,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
    SCAN_INTERVAL as SENSOR_DEFAULT_SCAN_INTERVAL,
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SCAN_INTERVAL as SWITCH_DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_COMMAND_TIMEOUT,
    CONF_JSON_ATTRIBUTES,
    CONF_JSON_ATTRIBUTES_PATH,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .helpers import async_load_platforms
from .services import async_setup_services

BINARY_SENSOR_DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
SENSOR_DEFAULT_NAME = "Command Sensor"
CONF_NOTIFIERS = "notifiers"

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COMMAND): cv.string,
        probatio.Optional(CONF_NAME, default=BINARY_SENSOR_DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_ICON): cv.template,
        probatio.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        probatio.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
            cv.template, ValueTemplate.from_template
        ),
        probatio.Optional(
            CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_int,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=BINARY_SENSOR_DEFAULT_SCAN_INTERVAL
        ): probatio.All(cv.time_period, cv.positive_timedelta),
        probatio.Optional(CONF_AVAILABILITY): cv.template,
    }
)
COVER_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_COMMAND_CLOSE, default="true"): cv.string,
        probatio.Optional(CONF_COMMAND_OPEN, default="true"): cv.string,
        probatio.Optional(CONF_COMMAND_STATE): cv.string,
        probatio.Optional(CONF_COMMAND_STOP, default="true"): cv.string,
        probatio.Required(CONF_NAME): cv.string,
        probatio.Optional(CONF_ICON): cv.template,
        probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
            cv.template, ValueTemplate.from_template
        ),
        probatio.Optional(
            CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_int,
        probatio.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=COVER_DEFAULT_SCAN_INTERVAL
        ): probatio.All(cv.time_period, cv.positive_timedelta),
        probatio.Optional(CONF_AVAILABILITY): cv.template,
    }
)
NOTIFY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COMMAND): cv.string,
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(
            CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_int,
    }
)
SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COMMAND): cv.string,
        probatio.Optional(
            CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_int,
        probatio.Optional(CONF_JSON_ATTRIBUTES): cv.ensure_list_csv,
        probatio.Optional(CONF_JSON_ATTRIBUTES_PATH): cv.string,
        probatio.Optional(CONF_NAME, default=SENSOR_DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_ICON): cv.template,
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
            cv.template, ValueTemplate.from_template
        ),
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=SENSOR_DEFAULT_SCAN_INTERVAL
        ): probatio.All(cv.time_period, cv.positive_timedelta),
        probatio.Optional(CONF_AVAILABILITY): cv.template,
    }
)
SWITCH_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_COMMAND_OFF, default="true"): cv.string,
        probatio.Optional(CONF_COMMAND_ON, default="true"): cv.string,
        probatio.Optional(CONF_COMMAND_STATE): cv.string,
        probatio.Required(CONF_NAME): cv.string,
        probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
            cv.template, ValueTemplate.from_template
        ),
        probatio.Optional(CONF_ICON): cv.template,
        probatio.Optional(
            CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_int,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=SWITCH_DEFAULT_SCAN_INTERVAL
        ): probatio.All(cv.time_period, cv.positive_timedelta),
        probatio.Optional(CONF_AVAILABILITY): cv.template,
    }
)
COMBINED_SCHEMA = probatio.Schema(
    {
        probatio.Optional(BINARY_SENSOR_DOMAIN): BINARY_SENSOR_SCHEMA,
        probatio.Optional(COVER_DOMAIN): COVER_SCHEMA,
        probatio.Optional(NOTIFY_DOMAIN): NOTIFY_SCHEMA,
        probatio.Optional(SENSOR_DOMAIN): SENSOR_SCHEMA,
        probatio.Optional(SWITCH_DOMAIN): SWITCH_SCHEMA,
    }
)
CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN): probatio.All(
            probatio.EnsureList(),
            [COMBINED_SCHEMA],
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Command Line from yaml config."""

    async_setup_services(hass)

    await async_load_platforms(hass, config.get(DOMAIN, []), config)

    return True
