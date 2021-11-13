"""The tcp component."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BUFFER_SIZE,
    CONF_VALUE_ON,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
)

DOMAIN = "tcp"

PLATFORMS = ["binary_sensor", "sensor"]

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

BASE_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

SENSOR_SCHEMA = BASE_SENSOR_SCHEMA.extend(
    {vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string}
)

BINARY_SENSOR_SCHEMA = BASE_SENSOR_SCHEMA.extend(
    {vol.Optional(CONF_VALUE_ON): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                HOST_SCHEMA.extend(
                    {
                        vol.Optional(CONF_SENSORS, default=[]): vol.All(
                            cv.ensure_list, [SENSOR_SCHEMA]
                        ),
                        vol.Optional(CONF_BINARY_SENSORS, default=[]): vol.All(
                            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TCP component."""
    for discovery_info in config[DOMAIN]:
        for platform in PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, platform, DOMAIN, discovery_info, config
                )
            )

    return True
