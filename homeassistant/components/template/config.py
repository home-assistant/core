"""Template config validator."""

from collections.abc import Callable
from contextlib import suppress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as DOMAIN_ALARM_CONTROL_PANEL,
)
from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.blueprint import (
    is_blueprint_instance_config,
    schemas as blueprint_schemas,
)
from homeassistant.components.button import DOMAIN as DOMAIN_BUTTON
from homeassistant.components.cover import DOMAIN as DOMAIN_COVER
from homeassistant.components.fan import DOMAIN as DOMAIN_FAN
from homeassistant.components.image import DOMAIN as DOMAIN_IMAGE
from homeassistant.components.light import DOMAIN as DOMAIN_LIGHT
from homeassistant.components.lock import DOMAIN as DOMAIN_LOCK
from homeassistant.components.number import DOMAIN as DOMAIN_NUMBER
from homeassistant.components.select import DOMAIN as DOMAIN_SELECT
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.components.vacuum import DOMAIN as DOMAIN_VACUUM
from homeassistant.components.weather import DOMAIN as DOMAIN_WEATHER
from homeassistant.config import async_log_schema_error, config_without_domain
from homeassistant.const import (
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_BINARY_SENSORS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TRIGGER,
    CONF_TRIGGERS,
    CONF_UNIQUE_ID,
    CONF_VARIABLES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import async_validate_conditions_config
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_notify_setup_error

from . import (
    alarm_control_panel as alarm_control_panel_platform,
    binary_sensor as binary_sensor_platform,
    button as button_platform,
    cover as cover_platform,
    fan as fan_platform,
    image as image_platform,
    light as light_platform,
    lock as lock_platform,
    number as number_platform,
    select as select_platform,
    sensor as sensor_platform,
    switch as switch_platform,
    vacuum as vacuum_platform,
    weather as weather_platform,
)
from .const import DOMAIN, PLATFORMS, TemplateConfig
from .helpers import async_get_blueprints

PACKAGE_MERGE_HINT = "list"


def ensure_domains_do_not_have_trigger_or_action(*keys: str) -> Callable[[dict], dict]:
    """Validate that config does not contain trigger and action."""
    domains = set(keys)

    def validate(obj: dict):
        options = set(obj.keys())
        if found_domains := domains.intersection(options):
            invalid = {CONF_TRIGGERS, CONF_ACTIONS}
            if found_invalid := invalid.intersection(set(obj.keys())):
                raise vol.Invalid(
                    f"Unsupported option(s) found for domain {found_domains.pop()}, please remove ({', '.join(found_invalid)}) from your configuration",
                )

        return obj

    return validate


def _backward_compat_schema(value: Any | None) -> Any:
    """Backward compatibility for automations."""

    value = cv.renamed(CONF_TRIGGER, CONF_TRIGGERS)(value)
    value = cv.renamed(CONF_ACTION, CONF_ACTIONS)(value)
    return cv.renamed(CONF_CONDITION, CONF_CONDITIONS)(value)


CONFIG_SECTION_SCHEMA = vol.All(
    _backward_compat_schema,
    vol.Schema(
        {
            vol.Optional(CONF_ACTIONS): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_BINARY_SENSORS): cv.schema_with_slug_keys(
                binary_sensor_platform.LEGACY_BINARY_SENSOR_SCHEMA
            ),
            vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
            vol.Optional(CONF_SENSORS): cv.schema_with_slug_keys(
                sensor_platform.LEGACY_SENSOR_SCHEMA
            ),
            vol.Optional(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Optional(DOMAIN_ALARM_CONTROL_PANEL): vol.All(
                cv.ensure_list,
                [alarm_control_panel_platform.ALARM_CONTROL_PANEL_SCHEMA],
            ),
            vol.Optional(DOMAIN_BINARY_SENSOR): vol.All(
                cv.ensure_list, [binary_sensor_platform.BINARY_SENSOR_SCHEMA]
            ),
            vol.Optional(DOMAIN_BUTTON): vol.All(
                cv.ensure_list, [button_platform.BUTTON_SCHEMA]
            ),
            vol.Optional(DOMAIN_COVER): vol.All(
                cv.ensure_list, [cover_platform.COVER_SCHEMA]
            ),
            vol.Optional(DOMAIN_FAN): vol.All(
                cv.ensure_list, [fan_platform.FAN_SCHEMA]
            ),
            vol.Optional(DOMAIN_IMAGE): vol.All(
                cv.ensure_list, [image_platform.IMAGE_SCHEMA]
            ),
            vol.Optional(DOMAIN_LIGHT): vol.All(
                cv.ensure_list, [light_platform.LIGHT_SCHEMA]
            ),
            vol.Optional(DOMAIN_LOCK): vol.All(
                cv.ensure_list, [lock_platform.LOCK_SCHEMA]
            ),
            vol.Optional(DOMAIN_NUMBER): vol.All(
                cv.ensure_list, [number_platform.NUMBER_SCHEMA]
            ),
            vol.Optional(DOMAIN_SELECT): vol.All(
                cv.ensure_list, [select_platform.SELECT_SCHEMA]
            ),
            vol.Optional(DOMAIN_SENSOR): vol.All(
                cv.ensure_list, [sensor_platform.SENSOR_SCHEMA]
            ),
            vol.Optional(DOMAIN_SWITCH): vol.All(
                cv.ensure_list, [switch_platform.SWITCH_SCHEMA]
            ),
            vol.Optional(DOMAIN_VACUUM): vol.All(
                cv.ensure_list, [vacuum_platform.VACUUM_SCHEMA]
            ),
            vol.Optional(DOMAIN_WEATHER): vol.All(
                cv.ensure_list, [weather_platform.WEATHER_SCHEMA]
            ),
        },
    ),
    ensure_domains_do_not_have_trigger_or_action(
        DOMAIN_ALARM_CONTROL_PANEL,
        DOMAIN_BUTTON,
        DOMAIN_COVER,
        DOMAIN_FAN,
        DOMAIN_LOCK,
        DOMAIN_VACUUM,
    ),
)

TEMPLATE_BLUEPRINT_SCHEMA = vol.All(
    _backward_compat_schema, blueprint_schemas.BLUEPRINT_SCHEMA
)


async def _async_resolve_blueprints(
    hass: HomeAssistant,
    config: ConfigType,
) -> TemplateConfig:
    """If a config item requires a blueprint, resolve that item to an actual config."""
    raw_config = None
    raw_blueprint_inputs = None

    with suppress(ValueError):  # Invalid config
        raw_config = dict(config)

    if is_blueprint_instance_config(config):
        blueprints = async_get_blueprints(hass)

        blueprint_inputs = await blueprints.async_inputs_from_config(
            _backward_compat_schema(config)
        )
        raw_blueprint_inputs = blueprint_inputs.config_with_inputs

        config = blueprint_inputs.async_substitute()

        platforms = [platform for platform in PLATFORMS if platform in config]
        if len(platforms) > 1:
            raise vol.Invalid("more than one platform defined per blueprint")
        if len(platforms) == 1:
            platform = platforms.pop()
            for prop in (CONF_NAME, CONF_UNIQUE_ID):
                if prop in config:
                    config[platform][prop] = config.pop(prop)
            # For regular template entities, CONF_VARIABLES should be removed because they just
            # house input results for template entities.  For Trigger based template entities
            # CONF_VARIABLES should not be removed because the variables are always
            # executed between the trigger and action.
            if CONF_TRIGGERS not in config and CONF_VARIABLES in config:
                config[platform][CONF_VARIABLES] = config.pop(CONF_VARIABLES)
        raw_config = dict(config)

    template_config = TemplateConfig(CONFIG_SECTION_SCHEMA(config))
    template_config.raw_blueprint_inputs = raw_blueprint_inputs
    template_config.raw_config = raw_config

    return template_config


async def async_validate_config_section(
    hass: HomeAssistant, config: ConfigType
) -> TemplateConfig:
    """Validate an entire config section for the template integration."""

    validated_config = await _async_resolve_blueprints(hass, config)

    if CONF_TRIGGERS in validated_config:
        validated_config[CONF_TRIGGERS] = await async_validate_trigger_config(
            hass, validated_config[CONF_TRIGGERS]
        )

    if CONF_CONDITIONS in validated_config:
        validated_config[CONF_CONDITIONS] = await async_validate_conditions_config(
            hass, validated_config[CONF_CONDITIONS]
        )

    return validated_config


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    if DOMAIN not in config:
        return config

    config_sections = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            template_config: TemplateConfig = await async_validate_config_section(
                hass, cfg
            )
        except vol.Invalid as err:
            async_log_schema_error(err, DOMAIN, cfg, hass)
            async_notify_setup_error(hass, DOMAIN)
            continue

        legacy_warn_printed = False

        for old_key, new_key, transform in (
            (
                CONF_SENSORS,
                DOMAIN_SENSOR,
                sensor_platform.rewrite_legacy_to_modern_conf,
            ),
            (
                CONF_BINARY_SENSORS,
                DOMAIN_BINARY_SENSOR,
                binary_sensor_platform.rewrite_legacy_to_modern_conf,
            ),
        ):
            if old_key not in template_config:
                continue

            if not legacy_warn_printed:
                legacy_warn_printed = True
                logging.getLogger(__name__).warning(
                    "The entity definition format under template: differs from the"
                    " platform "
                    "configuration format. See "
                    "https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
                )

            definitions = (
                list(template_config[new_key]) if new_key in template_config else []
            )
            definitions.extend(transform(hass, template_config[old_key]))
            template_config = TemplateConfig({**template_config, new_key: definitions})

        config_sections.append(template_config)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
