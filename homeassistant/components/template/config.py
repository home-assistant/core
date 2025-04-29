"""Template config validator."""

from collections.abc import Callable
from contextlib import suppress
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.blueprint import (
    BLUEPRINT_INSTANCE_FIELDS,
    is_blueprint_instance_config,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config import async_log_schema_error, config_without_domain
from homeassistant.const import (
    CONF_ACTIONS,
    CONF_BINARY_SENSORS,
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
from homeassistant.helpers.automation import backward_compatibility_schema
from homeassistant.helpers.condition import async_validate_conditions_config
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_notify_setup_error

from . import (
    binary_sensor as binary_sensor_platform,
    button as button_platform,
    cover as cover_platform,
    image as image_platform,
    light as light_platform,
    number as number_platform,
    select as select_platform,
    sensor as sensor_platform,
    switch as switch_platform,
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


CONFIG_SECTION_SCHEMA = vol.All(
    backward_compatibility_schema,
    vol.Schema(
        {
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_TRIGGERS): cv.TRIGGER_SCHEMA,
            vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
            vol.Optional(CONF_ACTIONS): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
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
            vol.Optional(LIGHT_DOMAIN): vol.All(
                cv.ensure_list, [light_platform.LIGHT_SCHEMA]
            ),
            vol.Optional(WEATHER_DOMAIN): vol.All(
                cv.ensure_list, [weather_platform.WEATHER_SCHEMA]
            ),
            vol.Optional(SWITCH_DOMAIN): vol.All(
                cv.ensure_list, [switch_platform.SWITCH_SCHEMA]
            ),
            vol.Optional(COVER_DOMAIN): vol.All(
                cv.ensure_list, [cover_platform.COVER_SCHEMA]
            ),
        },
    ),
    ensure_domains_do_not_have_trigger_or_action(
        BUTTON_DOMAIN, COVER_DOMAIN, LIGHT_DOMAIN
    ),
)

TEMPLATE_BLUEPRINT_INSTANCE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
).extend(BLUEPRINT_INSTANCE_FIELDS.schema)


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
        config = TEMPLATE_BLUEPRINT_INSTANCE_SCHEMA(config)
        blueprints = async_get_blueprints(hass)

        blueprint_inputs = await blueprints.async_inputs_from_config(config)
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
            if (
                not _is_trigger_based_template_entity(config)
                and CONF_VARIABLES in config
            ):
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
                SENSOR_DOMAIN,
                sensor_platform.rewrite_legacy_to_modern_conf,
            ),
            (
                CONF_BINARY_SENSORS,
                BINARY_SENSOR_DOMAIN,
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


def _is_trigger_based_template_entity(config):
    """Check if this is a trigger based template entity.

    Takes into account backwards compatible definition.
    """
    return CONF_TRIGGERS in config or CONF_TRIGGER in config
