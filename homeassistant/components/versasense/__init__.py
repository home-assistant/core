"""Support for VersaSense MicroPnP devices."""
import logging

import pyversasense as pyv
import voluptuous as vol

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    KEY_CONSUMER,
    KEY_IDENTIFIER,
    KEY_MEASUREMENT,
    KEY_PARENT_MAC,
    KEY_PARENT_NAME,
    KEY_UNIT,
    PERIPHERAL_CLASS_SENSOR,
    PERIPHERAL_CLASS_SENSOR_ACTUATOR,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "versasense"

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the versasense component."""
    session = aiohttp_client.async_get_clientsession(hass)
    consumer = pyv.Consumer(config[DOMAIN]["host"], session)

    hass.data[DOMAIN] = {KEY_CONSUMER: consumer}

    await _configure_entities(hass, config, consumer)

    # Return boolean to indicate that initialization was successful.
    return True


async def _configure_entities(hass, config, consumer):
    """Fetch all devices with their peripherals for representation."""
    devices = await consumer.fetchDevices()
    _LOGGER.debug(devices)

    sensor_info = {}
    switch_info = {}

    for mac, device in devices.items():
        _LOGGER.info("Device connected: %s %s", device.name, mac)
        hass.data[DOMAIN][mac] = {}

        for peripheral_id, peripheral in device.peripherals.items():
            hass.data[DOMAIN][mac][peripheral_id] = peripheral

            if peripheral.classification == PERIPHERAL_CLASS_SENSOR:
                sensor_info = _add_entity_info(peripheral, device, sensor_info)
            elif peripheral.classification == PERIPHERAL_CLASS_SENSOR_ACTUATOR:
                switch_info = _add_entity_info(peripheral, device, switch_info)

    if sensor_info:
        _load_platform(hass, config, Platform.SENSOR, sensor_info)

    if switch_info:
        _load_platform(hass, config, Platform.SWITCH, switch_info)


def _add_entity_info(peripheral, device, entity_dict) -> None:
    """Add info from a peripheral to specified list."""
    for measurement in peripheral.measurements:
        entity_info = {
            KEY_IDENTIFIER: peripheral.identifier,
            KEY_UNIT: measurement.unit,
            KEY_MEASUREMENT: measurement.name,
            KEY_PARENT_NAME: device.name,
            KEY_PARENT_MAC: device.mac,
        }

        key = f"{entity_info[KEY_PARENT_MAC]}/{entity_info[KEY_IDENTIFIER]}/{entity_info[KEY_MEASUREMENT]}"
        entity_dict[key] = entity_info

    return entity_dict


def _load_platform(hass, config, entity_type, entity_info):
    """Load platform with list of entity info."""
    hass.async_create_task(
        async_load_platform(hass, entity_type, DOMAIN, entity_info, config)
    )
