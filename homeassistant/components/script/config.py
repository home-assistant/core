"""Config validation helper for the script integration."""
import asyncio

import voluptuous as vol

from homeassistant.config import async_log_exception
from homeassistant.const import CONF_SEQUENCE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import async_validate_action_config

from . import DOMAIN, SCRIPT_ENTRY_SCHEMA


async def async_validate_config_item(hass, config, full_config=None):
    """Validate config item."""
    config = SCRIPT_ENTRY_SCHEMA(config)
    config[CONF_SEQUENCE] = await asyncio.gather(
        *[
            async_validate_action_config(hass, action)
            for action in config[CONF_SEQUENCE]
        ]
    )

    return config


async def _try_async_validate_config_item(hass, object_id, config, full_config=None):
    """Validate config item."""
    try:
        cv.slug(object_id)
        config = await async_validate_config_item(hass, config, full_config)
    except (vol.Invalid, HomeAssistantError) as ex:
        async_log_exception(ex, DOMAIN, full_config or config, hass)
        return None

    return config


async def async_validate_config(hass, config):
    """Validate config."""
    if DOMAIN in config:
        validated_config = {}
        for object_id, cfg in config[DOMAIN].items():
            cfg = await _try_async_validate_config_item(hass, object_id, cfg, config)
            if cfg is not None:
                validated_config[object_id] = cfg
        config[DOMAIN] = validated_config

    return config
