"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.group import \
        ENTITY_ID_FORMAT as GROUP_ENTITY_ID_FORMAT
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.const import (
    DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sensor'
DEPENDENCIES = ['group']

GROUP_NAME_ALL_SENSORS = 'all sensors'
ENTITY_ID_ALL_SENSORS = GROUP_ENTITY_ID_FORMAT.format('all_sensors')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=30)
DEVICE_CLASSES = [
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_SENSORS)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Setup a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)
