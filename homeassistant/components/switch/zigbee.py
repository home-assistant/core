"""
Contains functionality to use a Zigbee device as a switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zigbee/
"""
import voluptuous as vol

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.zigbee import (
    ZigBeeDigitalOut, ZigBeeDigitalOutConfig, PLATFORM_SCHEMA)

DEPENDENCIES = ['zigbee']

CONF_ON_STATE = 'on_state'

DEFAULT_ON_STATE = 'high'
DEPENDENCIES = ['zigbee']

STATES = ['high', 'low']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ON_STATE): vol.In(STATES),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Zigbee switch platform."""
    add_entities([ZigBeeSwitch(hass, ZigBeeDigitalOutConfig(config))])


class ZigBeeSwitch(ZigBeeDigitalOut, SwitchDevice):
    """Representation of a Zigbee Digital Out device."""

    pass
