"""Support for Zigbee binary sensors."""
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import PLATFORM_SCHEMA, ZigBeeDigitalIn, ZigBeeDigitalInConfig

CONF_ON_STATE = 'on_state'

DEFAULT_ON_STATE = 'high'
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
