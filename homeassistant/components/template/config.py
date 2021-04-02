"""Template config validator."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.trigger import async_validate_trigger_config

from .const import (
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_PICTURE,
    CONF_TRIGGER,
    DOMAIN,
)
from .sensor import SENSOR_SCHEMA as PLATFORM_SENSOR_SCHEMA

CONVERSION_PLATFORM = {
    CONF_ICON_TEMPLATE: CONF_ICON,
    CONF_ENTITY_PICTURE_TEMPLATE: CONF_PICTURE,
    CONF_AVAILABILITY_TEMPLATE: CONF_AVAILABILITY,
    CONF_ATTRIBUTE_TEMPLATES: CONF_ATTRIBUTES,
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
    CONF_FRIENDLY_NAME: CONF_NAME,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}


SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_ATTRIBUTES): vol.Schema({cv.string: cv.template}),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
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

        if CONF_SENSORS not in cfg:
            trigger_entity_configs.append(cfg)
            continue

        logging.getLogger(__name__).warning(
            "The entity definition format under template: differs from the platform configuration format. See https://www.home-assistant.io/integrations/template#configuration-for-trigger-based-template-sensors"
        )
        sensor = list(cfg[SENSOR_DOMAIN]) if SENSOR_DOMAIN in cfg else []

        for device_id, entity_cfg in cfg[CONF_SENSORS].items():
            entity_cfg = {**entity_cfg}

            for from_key, to_key in CONVERSION_PLATFORM.items():
                if from_key not in entity_cfg or to_key in entity_cfg:
                    continue

                val = entity_cfg.pop(from_key)
                if isinstance(val, str):
                    val = template.Template(val)
                entity_cfg[to_key] = val

            if CONF_NAME not in entity_cfg:
                entity_cfg[CONF_NAME] = template.Template(device_id)

            sensor.append(entity_cfg)

        cfg = {**cfg, "sensor": sensor}

        trigger_entity_configs.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = trigger_entity_configs

    return config
