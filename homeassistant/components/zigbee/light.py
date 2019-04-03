"""Support for Zigbee lights."""
import voluptuous as vol

from homeassistant.components.light import Light

from . import PLATFORM_SCHEMA, ZigBeeDigitalOut, ZigBeeDigitalOutConfig

CONF_ON_STATE = 'on_state'

DEFAULT_ON_STATE = 'high'
DEPENDENCIES = ['zigbee']

STATES = ['high', 'low']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ON_STATE, default=DEFAULT_ON_STATE): vol.In(STATES),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    add_entities([ZigBeeLight(hass, ZigBeeDigitalOutConfig(config))])


class ZigBeeLight(ZigBeeDigitalOut, Light):
    """Use ZigBeeDigitalOut as light."""

    pass
