"""
Functionality to use a ZigBee device as a light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zigbee/
"""
from homeassistant.components.light import Light
from homeassistant.components.zigbee import (
    ZigBeeDigitalOut, ZigBeeDigitalOutConfig)

DEPENDENCIES = ["zigbee"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        ZigBeeLight(hass, ZigBeeDigitalOutConfig(config))
    ])


class ZigBeeLight(ZigBeeDigitalOut, Light):
    """Use ZigBeeDigitalOut as light."""

    pass
