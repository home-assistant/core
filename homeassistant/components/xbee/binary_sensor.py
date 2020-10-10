"""Support for Zigbee binary sensors."""
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import DOMAIN, PLATFORM_SCHEMA, XBeeDigitalIn, XBeeDigitalInConfig

CONF_ON_STATE = "on_state"

DEFAULT_ON_STATE = "high"
STATES = ["high", "low"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_ON_STATE): vol.In(STATES)})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the XBee Zigbee binary sensor platform."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeBinarySensor(XBeeDigitalInConfig(config), zigbee_device)], True)


class XBeeBinarySensor(XBeeDigitalIn, BinarySensorEntity):
    """Use XBeeDigitalIn as binary sensor."""
