"""
homeassistant.components.light.zigbee

Contains functionality to use a ZigBee device as a light.
"""
from homeassistant.components.zigbee import (
    ZigBeeDigitalOut, ZigBeeDigitalOutConfig)


DEPENDENCIES = ["zigbee"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """
    Create and add an entity based on the configuration.
    """
    add_entities([
        ZigBeeDigitalOut(hass, ZigBeeDigitalOutConfig(config))
    ])
