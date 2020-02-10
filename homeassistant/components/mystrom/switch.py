"""Support for myStrom switches."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return myStrom switch."""
    from pymystrom.switch import MyStromPlug, exceptions

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        MyStromPlug(host).get_status()
    except exceptions.MyStromConnectionError:
        _LOGGER.error("No route to device: %s", host)
        raise PlatformNotReady()

    add_entities([MyStromSwitch(name, host)])


class MyStromSwitch(SwitchDevice):
    """Representation of a myStrom switch."""

    def __init__(self, name, resource):
        """Initialize the myStrom switch."""
        from pymystrom.switch import MyStromPlug

        self._name = name
        self._resource = resource
        self.data = {}
        self.plug = MyStromPlug(self._resource)
        self._available = True

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self.data["relay"])

    @property
    def current_power_w(self):
        """Return the current power consumption in W."""
        return round(self.data["power"], 2)

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from pymystrom import exceptions

        try:
            self.plug.set_relay_on()
        except exceptions.MyStromConnectionError:
            _LOGGER.error("No route to device: %s", self._resource)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from pymystrom import exceptions

        try:
            self.plug.set_relay_off()
        except exceptions.MyStromConnectionError:
            _LOGGER.error("No route to device: %s", self._resource)

    def update(self):
        """Get the latest data from the device and update the data."""
        from pymystrom import exceptions

        try:
            self.data = self.plug.get_status()
            self._available = True
        except exceptions.MyStromConnectionError:
            self.data = {"power": 0, "relay": False}
            self._available = False
            _LOGGER.error("No route to device: %s", self._resource)
