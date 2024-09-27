"""Template config validator."""

from contextlib import suppress
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.blueprint import is_blueprint_instance_config
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config import async_log_schema_error, config_without_domain
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import async_validate_conditions_config
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
from .const import CONF_ACTION, CONF_CONDITION, CONF_TRIGGER, DOMAIN, PLATFORMS
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "list"

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
        vol.Optional(CONF_CONDITION): cv.CONDITIONS_SCHEMA,
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


class TemplateConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None


async def _async_resolve_blueprints(
    hass: HomeAssistant,
    config: ConfigType,
    expected_platform: Platform,
) -> TemplateConfig:
    """If a config item requires a blueprint, resolve that item to an actual config."""
    raw_config = None
    raw_blueprint_inputs = None

    with suppress(ValueError):  # Invalid config
        raw_config = dict(config)

    if is_blueprint_instance_config(config):
        blueprints = async_get_blueprints(hass)

        blueprint_inputs = await blueprints.async_inputs_from_config(config)
        raw_blueprint_inputs = blueprint_inputs.config_with_inputs

        config = blueprint_inputs.async_substitute()
        if expected_platform not in config:
            raise vol.Invalid("Expected platform not in blueprint")
        for key, value in config[expected_platform].items():
            config[key] = value
        del config[expected_platform]
        raw_config = dict(config)

    template_config = TemplateConfig(config)
    template_config.raw_blueprint_inputs = raw_blueprint_inputs
    template_config.raw_config = raw_config

    return template_config


async def async_validate_config_section(hass: HomeAssistant, config: ConfigType):
    """Validate an entire config section for the template integration."""

    for platform in PLATFORMS:
        if platform not in config:
            continue

        config[platform] = cv.ensure_list(config[platform])
        for idx, cfg in enumerate(config[platform]):
            config[platform][idx] = await _async_resolve_blueprints(hass, cfg, platform)

    validated_config = CONFIG_SECTION_SCHEMA(config)

    if CONF_TRIGGER in validated_config:
        validated_config[CONF_TRIGGER] = await async_validate_trigger_config(
            hass, validated_config[CONF_TRIGGER]
        )

    if CONF_CONDITION in validated_config:
        validated_config[CONF_CONDITION] = await async_validate_conditions_config(
            hass, validated_config[CONF_CONDITION]
        )

    return validated_config


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    if DOMAIN not in config:
        return config

    config_sections = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = await async_validate_config_section(hass, cfg)
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
