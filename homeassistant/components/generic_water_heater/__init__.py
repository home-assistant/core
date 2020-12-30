"""The generic_water_heater integration."""
import logging

import voluptuous as vol

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "generic_water_heater"

CONF_HEATER = "heater_switch"
CONF_SENSOR = "temperature_sensor"
CONF_TARGET_TEMP = "target_temperature"
CONF_TEMP_DELTA = "delta_temperature"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.slug: vol.Schema(
                    {
                        vol.Required(CONF_HEATER): cv.entity_id,
                        vol.Required(CONF_SENSOR): cv.entity_id,
                        vol.Optional(CONF_TEMP_DELTA): vol.Coerce(float),
                        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, hass_config):
    """Set up Generic Water Heaters."""
    for water_heater, conf in hass_config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, water_heater)

        conf[CONF_NAME] = water_heater
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                WATER_HEATER_DOMAIN,
                DOMAIN,
                [conf],
                hass_config,
            )
        )
    return True
