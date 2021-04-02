"""Config validation helper for the script integration."""
import asyncio
from contextlib import suppress

import voluptuous as vol

from homeassistant.components.blueprint import (
    BlueprintInputs,
    is_blueprint_instance_config,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import (
    CONF_ALIAS,
    CONF_DEFAULT,
    CONF_DESCRIPTION,
    CONF_ICON,
    CONF_NAME,
    CONF_SELECTOR,
    CONF_SEQUENCE,
    CONF_VARIABLES,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, config_validation as cv
from homeassistant.helpers.script import (
    SCRIPT_MODE_SINGLE,
    async_validate_action_config,
    make_script_schema,
)
from homeassistant.helpers.selector import validate_selector

from .const import CONF_ADVANCED, CONF_EXAMPLE, CONF_FIELDS, CONF_REQUIRED, DOMAIN
from .helpers import async_get_blueprints

PLATFORM_SCHEMA = make_script_schema(
    {
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Required(CONF_SEQUENCE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DESCRIPTION, default=""): cv.string,
        vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
        vol.Optional(CONF_FIELDS, default={}): {
            cv.string: {
                vol.Optional(CONF_ADVANCED, default=False): cv.boolean,
                vol.Optional(CONF_DEFAULT): cv.match_all,
                vol.Optional(CONF_DESCRIPTION): cv.string,
                vol.Optional(CONF_EXAMPLE): cv.string,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_REQUIRED, default=False): cv.boolean,
                vol.Optional(CONF_SELECTOR): validate_selector,
            }
        },
    },
    SCRIPT_MODE_SINGLE,
)


async def async_validate_config_item(hass, config, full_config=None):
    """Validate config item."""
    if is_blueprint_instance_config(config):
        blueprints = async_get_blueprints(hass)
        return await blueprints.async_inputs_from_config(config)

    config = PLATFORM_SCHEMA(config)
    config[CONF_SEQUENCE] = await asyncio.gather(
        *[
            async_validate_action_config(hass, action)
            for action in config[CONF_SEQUENCE]
        ]
    )

    return config


class ScriptConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config = None


async def _try_async_validate_config_item(hass, object_id, config, full_config=None):
    """Validate config item."""

    raw_config = None
    with suppress(ValueError):  # Invalid config
        raw_config = dict(config)

    try:
        cv.slug(object_id)
        config = await async_validate_config_item(hass, config, full_config)
    except (vol.Invalid, HomeAssistantError) as ex:
        async_log_exception(ex, DOMAIN, full_config or config, hass)
        return None

    if isinstance(config, BlueprintInputs):
        return config

    config = ScriptConfig(config)
    config.raw_config = raw_config
    return config


async def async_validate_config(hass, config):
    """Validate config."""
    scripts = {}
    for _, p_config in config_per_platform(config, DOMAIN):
        for object_id, cfg in p_config.items():
            cfg = await _try_async_validate_config_item(hass, object_id, cfg, config)
            if cfg is not None:
                scripts[object_id] = cfg

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = scripts

    return config
