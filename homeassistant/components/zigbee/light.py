"""Support for Zigbee lights."""
import voluptuous as vol

from homeassistant.components.light import LightEntity

from . import DOMAIN, PLATFORM_SCHEMA, ZigBeeDigitalOut, ZigBeeDigitalOutConfig

CONF_ON_STATE = "on_state"

DEFAULT_ON_STATE = "high"
STATES = ["high", "low"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_ON_STATE, default=DEFAULT_ON_STATE): vol.In(STATES)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([ZigBeeLight(ZigBeeDigitalOutConfig(config), zigbee_device)])


class ZigBeeLight(ZigBeeDigitalOut, LightEntity):
    """Use ZigBeeDigitalOut as light."""
