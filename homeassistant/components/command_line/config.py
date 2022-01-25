"""Command Line config validator."""

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import (
    binary_sensor as binary_sensor_platform,
    cover as cover_platform,
    sensor as sensor_platform,
    switch as switch_platform,
)
from .const import DOMAIN

PACKAGE_MERGE_HINT = "list"

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [binary_sensor_platform.BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(COVER_DOMAIN): vol.All(
            cv.ensure_list, [cover_platform.COVER_SCHEMA]
        ),
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [sensor_platform.SENSOR_SCHEMA]
        ),
        vol.Optional(SWITCH_DOMAIN): vol.All(
            cv.ensure_list, [switch_platform.SWITCH_SCHEMA]
        ),
    }
)


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    if DOMAIN not in config:
        return config

    config_sections = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = CONFIG_SECTION_SCHEMA(cfg)

        except vol.Invalid as err:
            async_log_exception(err, DOMAIN, cfg, hass)
            continue

        config_sections.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
