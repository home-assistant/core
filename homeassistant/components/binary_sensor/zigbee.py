"""
Contains functionality to use a Zigbee device as a binary sensor.

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Zigbee binary sensor platform."""
    add_entities(
        [ZigBeeBinarySensor(hass, ZigBeeDigitalInConfig(config))], True)


class ZigBeeBinarySensor(ZigBeeDigitalIn, BinarySensorDevice):
    """Use ZigBeeDigitalIn as binary sensor."""

    pass
