"""Support for VersaSense MicroPnP devices."""
import logging

import pyversasense as pyv
import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import PERIPHERAL_CLASS_SENSOR, PERIPHERAL_CLASS_SENSOR_ACTUATOR

_LOGGER = logging.getLogger(__name__)

DOMAIN = "versasense"

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the versasense component."""
    session = aiohttp_client.async_get_clientsession(hass)
    consumer = pyv.Consumer(config[DOMAIN]['host'], session)

    hass.data[DOMAIN] = {
        'consumer': consumer
    }

    await _configure_entities(hass, config, consumer)

    # Return boolean to indicate that initialization was successful.
    return True


async def _configure_entities(hass, config, consumer):
    """Fetch all devices with their peripherals for representation."""
    devices = await consumer.fetchDevices()
    _LOGGER.debug(devices)
    for mac, device in devices.items():
        _LOGGER.info("Device connected: %s %s", device.name, mac)
        for peripheral_id, peripheral in device.peripherals.items():
            hass.data[DOMAIN][peripheral_id] = peripheral
            await _create_entity(hass, config, peripheral, device.name)


async def _create_entity(hass, config, peripheral, parent_name):
    """Create an entity based on a peripheral."""
    for measurement in peripheral.measurements:
        if peripheral.classification == PERIPHERAL_CLASS_SENSOR:
            entity_type = 'sensor'
        elif peripheral.classification == PERIPHERAL_CLASS_SENSOR_ACTUATOR:
            entity_type = 'switch'
        else:
            entity_type = None

        if entity_type is not None:
            hass.async_create_task(
                async_load_platform(
                    hass,
                    entity_type,
                    DOMAIN,
                    {
                        'identifier': peripheral.identifier,
                        'unit': measurement.unit,
                        'measurement': measurement.name,
                        'parent_name': parent_name
                    },
                    config
                )
            )
