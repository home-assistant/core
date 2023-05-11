"""Template config validator."""

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.blueprint import (
    BlueprintException,
    is_blueprint_instance_config,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import CONF_BINARY_SENSORS, CONF_SENSORS, CONF_UNIQUE_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.util.yaml.input import UndefinedSubstitution

from . import (
    binary_sensor as binary_sensor_platform,
    button as button_platform,
    number as number_platform,
    select as select_platform,
    sensor as sensor_platform,
)
from .const import CONF_BLUEPRINT_INPUTS, CONF_TRIGGER, DOMAIN, LOGGER
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "list"

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
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
    }
)


async def _async_validate_config_item(hass, config):
    """Validate template config item."""

    LOGGER.debug("Validating template config: %s", config)
    blueprint_inputs = None
    if is_blueprint_instance_config(config):
        blueprints = async_get_blueprints(hass)

        try:
            blueprint_inputs = await blueprints.async_inputs_from_config(config)
        except BlueprintException as err:
            LOGGER.error(
                "Failed to generate template from blueprint: %s",
                err,
            )
            raise

        LOGGER.debug("Blueprint inputs: %s", blueprint_inputs.inputs)

        try:
            config = blueprint_inputs.async_substitute()
        except UndefinedSubstitution as err:
            LOGGER.error(
                "Blueprint '%s' failed to generate template with inputs %s: %s",
                blueprint_inputs.blueprint.name,
                blueprint_inputs.inputs,
                err,
            )
            raise HomeAssistantError from err

    config = CONFIG_SECTION_SCHEMA(config)
    # Add blueprint inputs to entity config
    if blueprint_inputs:
        for dom in (
            BINARY_SENSOR_DOMAIN,
            BUTTON_DOMAIN,
            NUMBER_DOMAIN,
            SELECT_DOMAIN,
            SENSOR_DOMAIN,
        ):
            if dom in config:
                for idx in range(len(config[dom])):
                    config[dom][idx][CONF_BLUEPRINT_INPUTS] = {
                        "blueprint": blueprint_inputs.inputs
                    }
        LOGGER.debug("Blueprint final config: %s", config)

    if CONF_TRIGGER in config:
        config[CONF_TRIGGER] = await async_validate_trigger_config(
            hass, config[CONF_TRIGGER]
        )
    return config


async def async_validate_config(hass, config):
    """Validate config."""
    if DOMAIN not in config:
        return config

    config_sections = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = await _async_validate_config_item(hass, cfg)
        except vol.Invalid as err:
            async_log_exception(err, DOMAIN, cfg, hass)
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
                LOGGER.warning(
                    "The entity definition format under template: differs from the"
                    " platform "
                    "configuration format. See "
                    "https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
                )

            definitions = list(cfg[new_key]) if new_key in cfg else []
            definitions.extend(transform(cfg[old_key]))
            cfg = {**cfg, new_key: definitions}

        config_sections.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
