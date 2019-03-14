"""Sensor platform for mobile_app."""
from .const import ATTR_SENSOR_TYPE_SENSOR as ENTITY_TYPE

from .entity import (async_setup_mobile_app_entry,
                     async_setup_mobile_app_platform)

DEPENDENCIES = ['mobile_app']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the mobile app sensor."""
    return await async_setup_mobile_app_platform(ENTITY_TYPE,
                                                 hass, config,
                                                 async_add_entities,
                                                 discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app sensor from a config entry."""
    return await async_setup_mobile_app_entry(ENTITY_TYPE, hass, config_entry,
                                              async_add_entities)
