"""Support for Zigbee switches."""
import voluptuous as vol

from homeassistant.components.switch import SwitchDevice

from . import PLATFORM_SCHEMA, ZigBeeDigitalOut, ZigBeeDigitalOutConfig

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
