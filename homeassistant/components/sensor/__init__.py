"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.const import (
    DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_TIMESTAMP, DEVICE_CLASS_PRESSURE)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=30)
DEVICE_CLASSES = [
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
    DEVICE_CLASS_TIMESTAMP,  # timestamp (ISO8601)
    DEVICE_CLASS_PRESSURE,  # pressure (hPa/mbar)
]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)
