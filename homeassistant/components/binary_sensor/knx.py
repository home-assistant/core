"""
Contains functionality to use a KNX group address as a binary.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.knx/
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.knx import (
    KNXConfig, KNXGroupAddress)

DEPENDENCIES = ["knx"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([
        KNXSwitch(hass, KNXConfig(config))
    ])


class KNXSwitch(KNXGroupAddress, BinarySensorDevice):
    """Representation of a KNX sensor device."""

    pass
