"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging

from homeassistant.const import CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL
from homeassistant.helpers import validate_config, discovery
from homeassistant.helpers.entity import ToggleEntity

DOMAIN = "wink"
REQUIREMENTS = ['python-wink==0.7.7']


def setup(hass, config):
    """Setup the Wink component."""
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_ACCESS_TOKEN]}, logger):
        return False

    import pywink
    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])

    # Load components for the devices in the Wink that we support
    for component_name, func_exists in (
            ('light', pywink.get_bulbs),
            ('switch', lambda: pywink.get_switches or pywink.get_sirens or
             pywink.get_powerstrip_outlets),
            ('binary_sensor', pywink.get_sensors),
            ('sensor', lambda: pywink.get_sensors or pywink.get_eggtrays),
            ('lock', pywink.get_locks),
            ('rollershutter', pywink.get_shades),
            ('garage_door', pywink.get_garage_doors)):

        if func_exists():
            discovery.load_platform(hass, component_name, DOMAIN, {}, config)

    return True


class WinkToggleDevice(ToggleEntity):
    """Represents a Wink toggle (switch) device."""

    def __init__(self, wink):
        """Initialize the Wink device."""
        self.wink = wink
        self._battery = self.wink.battery_level

    @property
    def unique_id(self):
        """Return the ID of this Wink device."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the device."""
        return self.wink.name()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)

    def update(self):
        """Update state of the device."""
        self.wink.update_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
        return self.wink.battery_level * 100
