"""The Yr component."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_FORECAST, DEFAULT_FORECAST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ELEVATION): vol.Coerce(int),
        vol.Optional(CONF_FORECAST, default=DEFAULT_FORECAST): vol.Coerce(int),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [COMPONENT_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up Yr sensors from legacy config file."""

    confs = config.get(DOMAIN)
    if confs is None:
        return True

    for conf in confs:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Yr sensors."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Yr sensors."""
    return await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
