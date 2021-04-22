"""Template config validator."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import CONF_SENSORS, CONF_UNIQUE_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import async_validate_trigger_config

from . import sensor as sensor_platform
from .const import CONF_TRIGGER, DOMAIN

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [sensor_platform.SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_SENSORS): cv.schema_with_slug_keys(
            sensor_platform.LEGACY_SENSOR_SCHEMA
        ),
    }
)


async def async_validate_config(hass, config):
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
            async_log_exception(err, DOMAIN, cfg, hass)
            continue

        if CONF_SENSORS in cfg:
            logging.getLogger(__name__).warning(
                "The entity definition format under template: differs from the platform "
                "configuration format. See "
                "https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
            )
            sensors = list(cfg[SENSOR_DOMAIN]) if SENSOR_DOMAIN in cfg else []
            sensors.extend(
                sensor_platform.rewrite_legacy_to_modern_conf(cfg[CONF_SENSORS])
            )
            cfg = {**cfg, "sensor": sensors}

        config_sections.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
