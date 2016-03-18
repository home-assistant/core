"""
Contains functionality to use a ZigBee device as a binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.zigbee/
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.zigbee import (
    ZigBeeDigitalIn, ZigBeeDigitalInConfig)

DEPENDENCIES = ["zigbee"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        ZigBeeBinarySensor(hass, ZigBeeDigitalInConfig(config))
    ])


class ZigBeeBinarySensor(ZigBeeDigitalIn, BinarySensorDevice):
    """Use ZigBeeDigitalIn as binary sensor."""

    pass
