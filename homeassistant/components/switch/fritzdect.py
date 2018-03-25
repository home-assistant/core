"""
Support for FRITZ!DECT Switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fritzdect/
"""
import logging

from requests.exceptions import RequestException, HTTPError

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

REQUIREMENTS = ['fritzhome==1.0.4']

_LOGGER = logging.getLogger(__name__)

# Standard Fritz Box IP
DEFAULT_HOST = 'fritz.box'

ATTR_CURRENT_CONSUMPTION = 'current_consumption'
ATTR_CURRENT_CONSUMPTION_UNIT = 'current_consumption_unit'
ATTR_CURRENT_CONSUMPTION_UNIT_VALUE = 'W'

ATTR_TOTAL_CONSUMPTION = 'total_consumption'
ATTR_TOTAL_CONSUMPTION_UNIT = 'total_consumption_unit'
ATTR_TOTAL_CONSUMPTION_UNIT_VALUE = 'kWh'

ATTR_TEMPERATURE_UNIT = 'temperature_unit'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add all switches connected to Fritz Box."""
    from fritzhome.fritz import FritzBox

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    # Log into Fritz Box
    fritz = FritzBox(host, username, password)
    try:
        fritz.login()
    except Exception:  # pylint: disable=W0703
        _LOGGER.error("Login to Fritz!Box failed")
        return

    # Add all actors to hass
    for actor in fritz.get_actors():
        # Only add devices that support switching
        if actor.has_switch:
            data = FritzDectSwitchData(fritz, actor.actor_id)
            data.is_online = True
            add_devices([FritzDectSwitch(hass, data, actor.name)], True)


class FritzDectSwitch(SwitchDevice):
    """Representation of a FRITZ!DECT switch."""

    def __init__(self, hass, data, name):
        """Initialize the switch."""
        self.units = hass.config.units
        self.data = data
        self._name = name

    @property
    def name(self):
        """Return the name of the FRITZ!DECT switch, if any."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {}

        if self.data.has_powermeter and \
           self.data.current_consumption is not None and \
           self.data.total_consumption is not None:
            attrs[ATTR_CURRENT_CONSUMPTION] = "{:.1f}".format(
                self.data.current_consumption)
            attrs[ATTR_CURRENT_CONSUMPTION_UNIT] = "{}".format(
                ATTR_CURRENT_CONSUMPTION_UNIT_VALUE)
            attrs[ATTR_TOTAL_CONSUMPTION] = "{:.3f}".format(
                self.data.total_consumption)
            attrs[ATTR_TOTAL_CONSUMPTION_UNIT] = "{}".format(
                ATTR_TOTAL_CONSUMPTION_UNIT_VALUE)

        if self.data.has_temperature and \
           self.data.temperature is not None:
            attrs[ATTR_TEMPERATURE] = "{}".format(
                self.units.temperature(self.data.temperature, TEMP_CELSIUS))
            attrs[ATTR_TEMPERATURE_UNIT] = "{}".format(
                self.units.temperature_unit)
        return attrs

    @property
    def current_power_watt(self):
        """Return the current power usage in Watt."""
        try:
            return float(self.data.current_consumption)
        except ValueError:
            return None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.data.state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if not self.data.is_online:
            _LOGGER.error("turn_on: Not online skipping request")
            return

        try:
            actor = self.data.fritz.get_actor_by_ain(self.data.ain)
            actor.switch_on()
        except (RequestException, HTTPError):
            _LOGGER.error("Fritz!Box query failed, triggering relogin")
            self.data.is_online = False

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if not self.data.is_online:
            _LOGGER.error("turn_off: Not online skipping request")
            return

        try:
            actor = self.data.fritz.get_actor_by_ain(self.data.ain)
            actor.switch_off()
        except (RequestException, HTTPError):
            _LOGGER.error("Fritz!Box query failed, triggering relogin")
            self.data.is_online = False

    def update(self):
        """Get the latest data from the fritz box and updates the states."""
        if not self.data.is_online:
            _LOGGER.error("update: Not online, logging back in")

            try:
                self.data.fritz.login()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Login to Fritz!Box failed")
                return

            self.data.is_online = True

        try:
            self.data.update()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Fritz!Box query failed, triggering relogin")
            self.data.is_online = False


class FritzDectSwitchData(object):
    """Get the latest data from the fritz box."""

    def __init__(self, fritz, ain):
        """Initialize the data object."""
        self.fritz = fritz
        self.ain = ain
        self.state = None
        self.temperature = None
        self.current_consumption = None
        self.total_consumption = None
        self.has_switch = False
        self.has_temperature = False
        self.has_powermeter = False
        self.is_online = False

    def update(self):
        """Get the latest data from the fritz box."""
        if not self.is_online:
            _LOGGER.error("Not online skipping request")
            return

        try:
            actor = self.fritz.get_actor_by_ain(self.ain)
        except (RequestException, HTTPError):
            _LOGGER.error("Request to actor registry failed")
            self.state = None
            self.temperature = None
            self.current_consumption = None
            self.total_consumption = None
            raise Exception('Request to actor registry failed')

        if actor is None:
            _LOGGER.error("Actor could not be found")
            self.state = None
            self.temperature = None
            self.current_consumption = None
            self.total_consumption = None
            raise Exception('Actor could not be found')

        try:
            self.state = actor.get_state()
            self.current_consumption = (actor.get_power() or 0.0) / 1000
            self.total_consumption = (actor.get_energy() or 0.0) / 100000
        except (RequestException, HTTPError):
            _LOGGER.error("Request to actor failed")
            self.state = None
            self.temperature = None
            self.current_consumption = None
            self.total_consumption = None
            raise Exception('Request to actor failed')

        self.temperature = actor.temperature
        self.has_switch = actor.has_switch
        self.has_temperature = actor.has_temperature
        self.has_powermeter = actor.has_powermeter
