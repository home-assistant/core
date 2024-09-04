"""Template config validator."""

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config import async_log_schema_error, config_without_domain
from homeassistant.const import CONF_BINARY_SENSORS, CONF_SENSORS, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_notify_setup_error

from . import (
    binary_sensor as binary_sensor_platform,
    button as button_platform,
    image as image_platform,
    number as number_platform,
    select as select_platform,
    sensor as sensor_platform,
    weather as weather_platform,
)
from .const import CONF_ACTION, CONF_TRIGGER, DOMAIN

PACKAGE_MERGE_HINT = "list"

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
        vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(NUMBER_DOMAIN): vol.All(
            cv.ensure_list, [number_platform.NUMBER_SCHEMA]
        ),
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [sensor_platform.SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_SENSORS): cv.schema_with_slug_keys(
            sensor_platform.LEGACY_SENSOR_SCHEMA
        ),
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [binary_sensor_platform.BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_BINARY_SENSORS): cv.schema_with_slug_keys(
            binary_sensor_platform.LEGACY_BINARY_SENSOR_SCHEMA
        ),
        vol.Optional(SELECT_DOMAIN): vol.All(
            cv.ensure_list, [select_platform.SELECT_SCHEMA]
        ),
        vol.Optional(BUTTON_DOMAIN): vol.All(
            cv.ensure_list, [button_platform.BUTTON_SCHEMA]
        ),
        vol.Optional(IMAGE_DOMAIN): vol.All(
            cv.ensure_list, [image_platform.IMAGE_SCHEMA]
        ),
        vol.Optional(WEATHER_DOMAIN): vol.All(
            cv.ensure_list, [weather_platform.WEATHER_SCHEMA]
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

            if CONF_TRIGGER in cfg:
                cfg[CONF_TRIGGER] = await async_validate_trigger_config(
                    hass, cfg[CONF_TRIGGER]
                )
        except vol.Invalid as err:
            async_log_schema_error(err, DOMAIN, cfg, hass)
            async_notify_setup_error(hass, DOMAIN)
            continue

        legacy_warn_printed = False

        for old_key, new_key, transform in (
            (
                CONF_SENSORS,
                SENSOR_DOMAIN,
                sensor_platform.rewrite_legacy_to_modern_conf,
            ),
            (
                CONF_BINARY_SENSORS,
                BINARY_SENSOR_DOMAIN,
                binary_sensor_platform.rewrite_legacy_to_modern_conf,
            ),
        ):
            if old_key not in cfg:
                continue

            if not legacy_warn_printed:
                legacy_warn_printed = True
                logging.getLogger(__name__).warning(
                    "The entity definition format under template: differs from the"
                    " platform "
                    "configuration format. See "
                    "https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
                )

            definitions = list(cfg[new_key]) if new_key in cfg else []
            definitions.extend(transform(hass, cfg[old_key]))
            cfg = {**cfg, new_key: definitions}

        config_sections.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
