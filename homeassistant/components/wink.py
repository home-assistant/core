"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, CONF_ACCESS_TOKEN,
    EVENT_PLATFORM_DISCOVERED, ATTR_BATTERY_LEVEL)
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.loader import get_component

DOMAIN = "wink"
REQUIREMENTS = ['python-wink==0.7.6']

DISCOVER_LIGHTS = "wink.lights"
DISCOVER_SWITCHES = "wink.switches"
DISCOVER_SENSORS = "wink.sensors"
DISCOVER_BINARY_SENSORS = "wink.binary_sensors"
DISCOVER_LOCKS = "wink.locks"
DISCOVER_GARAGE_DOORS = "wink.garage_doors"


def setup(hass, config):
    """Setup the Wink component."""
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_ACCESS_TOKEN]}, logger):
        return False

    import pywink
    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])

    # Load components for the devices in the Wink that we support
    for component_name, func_exists, discovery_type in (
            ('light', pywink.get_bulbs, DISCOVER_LIGHTS),
            ('switch', lambda: pywink.get_switches or
             pywink.get_sirens or
             pywink.get_powerstrip_outlets, DISCOVER_SWITCHES),
            ('binary_sensor', pywink.get_sensors, DISCOVER_BINARY_SENSORS),
            ('sensor', lambda: pywink.get_sensors or
             pywink.get_eggtrays, DISCOVER_SENSORS),
            ('lock', pywink.get_locks, DISCOVER_LOCKS),
            ('garage_door', pywink.get_garage_doors, DISCOVER_GARAGE_DOORS)):

        if func_exists():
            component = get_component(component_name)

            # Ensure component is loaded
            bootstrap.setup_component(hass, component.DOMAIN, config)

            # Fire discovery event
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_type,
                ATTR_DISCOVERED: {}
            })

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
