"""Template config validator."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.trigger import async_validate_trigger_config

from .const import CONF_TRIGGER, DOMAIN
from .sensor import SENSOR_BASE_SCHEMA, SENSOR_SCHEMA as PLATFORM_SENSOR_SCHEMA

CONF_STATE = "state"


SENSOR_SCHEMA = vol.Schema(
    {
        **SENSOR_BASE_SCHEMA,
        vol.Optional(CONF_NAME): cv.template,
    }
)

TRIGGER_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_TRIGGER): cv.TRIGGER_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
        vol.Optional(CONF_SENSORS): cv.schema_with_slug_keys(PLATFORM_SENSOR_SCHEMA),
    }
)


async def async_validate_config(hass, config):
    """Validate config."""
    if DOMAIN not in config:
        return config

    trigger_entity_configs = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = TRIGGER_ENTITY_SCHEMA(cfg)
            cfg[CONF_TRIGGER] = await async_validate_trigger_config(
                hass, cfg[CONF_TRIGGER]
            )
        except vol.Invalid as err:
            async_log_exception(err, DOMAIN, cfg, hass)
            continue

        if CONF_SENSORS in cfg:
            logging.getLogger(__name__).warning(
                "The entity definition format under template: differs from the platform configuration format. See https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
            )
            sensor = list(cfg[SENSOR_DOMAIN]) if SENSOR_DOMAIN in cfg else []

            for device_id, entity_cfg in cfg[CONF_SENSORS].items():
                if CONF_NAME not in entity_cfg:
                    for name in (
                        entity_cfg.get(CONF_FRIENDLY_NAME_TEMPLATE),
                        entity_cfg.get(CONF_FRIENDLY_NAME),
                        device_id,
                    ):
                        if name is None:
                            continue

                        if not isinstance(name, template.Template):
                            name = template.Template(name)

                        entity_cfg = {
                            **entity_cfg,
                            CONF_NAME: name,
                        }
                        break

                sensor.append(entity_cfg)

            cfg = {**cfg, "sensor": sensor}

        trigger_entity_configs.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = trigger_entity_configs

    return config
