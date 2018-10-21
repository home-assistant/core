"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""

from datetime import timedelta
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.core import ServiceCall
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.const import (
    DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_PRESSURE, ATTR_ENTITY_ID)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=30)
DEVICE_CLASSES = [
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
    DEVICE_CLASS_PRESSURE,  # pressure (hPa/mbar)
]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

SERVICE_FORCE_UPDATE = "force_update"
SENSOR_UPDATE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id
})


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)

    async def async_schedule_forced_update(call: ServiceCall):
        """Handle sensor force_update service calls"""
        entity_id = call.data[ATTR_ENTITY_ID]
        entity = component.get_entity(entity_id)
        entity.async_schedule_update_ha_state(True)

    hass.services.async_register(DOMAIN, SERVICE_FORCE_UPDATE,
                                 async_schedule_forced_update,
                                 SENSOR_UPDATE_SERVICE_SCHEMA)

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)
