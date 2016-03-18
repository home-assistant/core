"""
Contains functionality to use a ZigBee device as a switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zigbee/
"""
from homeassistant.components.switch import SwitchDevice
from homeassistant.components.zigbee import (
    ZigBeeDigitalOut, ZigBeeDigitalOutConfig)

DEPENDENCIES = ["zigbee"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        ZigBeeSwitch(hass, ZigBeeDigitalOutConfig(config))
    ])


class ZigBeeSwitch(ZigBeeDigitalOut, SwitchDevice):
    """Representation of a ZigBee Digital Out device."""

    pass
