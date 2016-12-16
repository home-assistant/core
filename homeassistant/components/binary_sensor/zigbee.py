"""
Contains functionality to use a ZigBee device as a binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.zigbee/
"""
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.zigbee import (
    ZigBeeDigitalIn, ZigBeeDigitalInConfig, PLATFORM_SCHEMA)

CONF_ON_STATE = 'on_state'

DEFAULT_ON_STATE = 'high'
DEPENDENCIES = ['zigbee']

STATES = ['high', 'low']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ON_STATE): vol.In(STATES),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZigBee binary sensor platform."""
    add_devices([ZigBeeBinarySensor(hass, ZigBeeDigitalInConfig(config))])


class ZigBeeBinarySensor(ZigBeeDigitalIn, BinarySensorDevice):
    """Use ZigBeeDigitalIn as binary sensor."""

    pass
