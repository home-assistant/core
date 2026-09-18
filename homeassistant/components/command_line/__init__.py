"""The command_line component."""

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

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
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
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

BINARY_SENSOR_DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
SENSOR_DEFAULT_NAME = "Command Sensor"
CONF_NOTIFIERS = "notifiers"

PLATFORM_MAPPING = {
    BINARY_SENSOR_DOMAIN: Platform.BINARY_SENSOR,
    COVER_DOMAIN: Platform.COVER,
    NOTIFY_DOMAIN: Platform.NOTIFY,
    SENSOR_DOMAIN: Platform.SENSOR,
    SWITCH_DOMAIN: Platform.SWITCH,
}

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
            cv.ensure_list,
            [COMBINED_SCHEMA],
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Command Line from yaml config."""

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload Command Line."""
        reload_config = await async_integration_yaml_config(hass, DOMAIN)
        reset_platforms = async_get_platforms(hass, DOMAIN)
        for reset_platform in reset_platforms:
            _LOGGER.debug("Reload resetting platform: %s", reset_platform.domain)
            await reset_platform.async_reset()
        if not reload_config:
            return
        await async_load_platforms(hass, reload_config.get(DOMAIN, []), reload_config)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    await async_load_platforms(hass, config.get(DOMAIN, []), config)

    return True


async def async_load_platforms(
    hass: HomeAssistant,
    command_line_config: list[dict[str, dict[str, Any]]],
    config: ConfigType,
) -> None:
    """Load platforms from yaml."""
    if not command_line_config:
        return

    _LOGGER.debug("Full config loaded: %s", command_line_config)

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    platforms: list[Platform] = []
    reload_configs: list[tuple[Platform, dict[str, Any]]] = []
    for platform_config in command_line_config:
        for platform, _config in platform_config.items():
            if (mapped_platform := PLATFORM_MAPPING[platform]) not in platforms:
                platforms.append(mapped_platform)
            _LOGGER.debug(
                "Loading config %s for platform %s",
                platform_config,
                PLATFORM_MAPPING[platform],
            )
            reload_configs.append((PLATFORM_MAPPING[platform], _config))
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    PLATFORM_MAPPING[platform],
                    DOMAIN,
                    _config,
                    config,
                )
            )

    if load_coroutines:
        _LOGGER.debug("Loading platforms: %s", platforms)
        await asyncio.gather(*load_coroutines)
