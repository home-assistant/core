"""
Support for texecom zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.texecom/
"""

import asyncio
import logging

from homeassistant.components.texecom import (
    CONF_ZONENAME, CONF_ZONENUMBER, CONF_ZONETYPE,
    ZONE_SCHEMA, TexecomBinarySensor)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['texecom']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Texecom binary sensor devices."""
    _LOGGER.info('Setting Up Binary Sensors')
    configured_zones = discovery_info['zones']

    devices = []
    for zone_num in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        _LOGGER.info('Setting Up Binary Sensors %s', hass)

        device = TexecomBinarySensor(
            hass,
            device_config_data[CONF_ZONENUMBER],
            device_config_data[CONF_ZONENAME],
            device_config_data[CONF_ZONETYPE],
            False
        )
        devices.append(device)

    async_add_devices(devices)
