"""
Functionality to use a ZigBee device as a light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zigbee/
"""
import voluptuous as vol

from homeassistant.components.light import Light
from homeassistant.components.zigbee import (
    ZigBeeDigitalOut, ZigBeeDigitalOutConfig, PLATFORM_SCHEMA)

CONF_ON_STATE = 'on_state'

DEFAULT_ON_STATE = 'high'
DEPENDENCIES = ['zigbee']

STATES = ['high', 'low']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ON_STATE, default=DEFAULT_ON_STATE): vol.In(STATES),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_devices([ZigBeeLight(hass, ZigBeeDigitalOutConfig(config))])


class ZigBeeLight(ZigBeeDigitalOut, Light):
    """Use ZigBeeDigitalOut as light."""

    pass
