"""Support for XBee Zigbee switches."""
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, PLATFORM_SCHEMA, XBeeDigitalOut, XBeeDigitalOutConfig

CONF_ON_STATE = "on_state"

DEFAULT_ON_STATE = "high"

STATES = ["high", "low"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_ON_STATE): vol.In(STATES)})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the XBee Zigbee switch platform."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeSwitch(XBeeDigitalOutConfig(config), zigbee_device)])


class XBeeSwitch(XBeeDigitalOut, SwitchEntity):
    """Representation of a XBee Zigbee Digital Out device."""
