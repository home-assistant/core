"""Trigger entity config platform."""

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import async_validate_trigger_config

from .const import DOMAIN

CONF_TRIGGER = "trigger"
CONF_STATE = "state"


TRIGGER_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
        vol.Required(SENSOR_DOMAIN): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_UNIQUE_ID): cv.string,
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
                        vol.Required(CONF_STATE): cv.template,
                    }
                )
            ],
        ),
    }
)


async def async_validate_config(hass, config):
    """Validate config."""
    trigger_entity_configs = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = TRIGGER_ENTITY_SCHEMA(cfg)
            cfg[CONF_TRIGGER] = await async_validate_trigger_config(
                hass, cfg[CONF_TRIGGER]
            )
            trigger_entity_configs.append(cfg)
        except vol.Invalid as err:
            assert False
            async_log_exception(err, DOMAIN, cfg, hass)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = trigger_entity_configs

    return config
