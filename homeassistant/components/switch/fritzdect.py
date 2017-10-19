"""
Support for FRITZ!DECT Switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fritzdect/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE, STATE_UNKNOWN

REQUIREMENTS = ['fritzhome==1.0.3']

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

    # Hack: fritzhome only throws Exception. To prevent pylint from
    # complaining, we disable the warning here:
    # pylint: disable=W0703

    # Log into Fritz Box
    fritz = FritzBox(host, username, password)
    try:
        fritz.login()
    except Exception:
        _LOGGER.error("Login to Fritz!Box failed")
        return

    # Add all actors to hass
    for actor in fritz.get_actors():
        # Only add devices that support switching
        if actor.has_switch:
            data = FritzDectSwitchData(fritz, actor.actor_id)
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
           self.data.current_consumption != STATE_UNKNOWN and \
           self.data.total_consumption != STATE_UNKNOWN:
            attrs[ATTR_CURRENT_CONSUMPTION] = "{:.1f}".format(
                self.data.current_consumption)
            attrs[ATTR_CURRENT_CONSUMPTION_UNIT] = "{}".format(
                ATTR_CURRENT_CONSUMPTION_UNIT_VALUE)
            attrs[ATTR_TOTAL_CONSUMPTION] = "{:.3f}".format(
                self.data.total_consumption)
            attrs[ATTR_TOTAL_CONSUMPTION_UNIT] = "{}".format(
                ATTR_TOTAL_CONSUMPTION_UNIT_VALUE)

        if self.data.has_temperature and \
           self.data.temperature != STATE_UNKNOWN:
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
        actor = self.data.fritz.get_actor_by_ain(self.data.ain)
        actor.switch_on()

    def turn_off(self):
        """Turn the switch off."""
        actor = self.data.fritz.get_actor_by_ain(self.data.ain)
        actor.switch_off()

    def update(self):
        """Get the latest data from the fritz box and updates the states."""
        self.data.update()


class FritzDectSwitchData(object):
    """Get the latest data from the fritz box."""

    def __init__(self, fritz, ain):
        """Initialize the data object."""
        self.fritz = fritz
        self.ain = ain
        self.state = STATE_UNKNOWN
        self.temperature = STATE_UNKNOWN
        self.current_consumption = STATE_UNKNOWN
        self.total_consumption = STATE_UNKNOWN
        self.has_switch = STATE_UNKNOWN
        self.has_temperature = STATE_UNKNOWN
        self.has_powermeter = STATE_UNKNOWN

    def update(self):
        """Get the latest data from the fritz box."""
        from requests.exceptions import RequestException

        try:
            actor = self.fritz.get_actor_by_ain(self.ain)
            self.state = actor.get_state()
        except RequestException:
            _LOGGER.error("Request to actor failed")
            self.state = STATE_UNKNOWN
            self.temperature = STATE_UNKNOWN
            self.current_consumption = STATE_UNKNOWN
            self.total_consumption = STATE_UNKNOWN
            return

        self.temperature = actor.temperature
        self.current_consumption = (actor.get_power() or 0.0) / 1000
        self.total_consumption = (actor.get_energy() or 0.0) / 100000
        self.has_switch = actor.has_switch
        self.has_temperature = actor.has_temperature
        self.has_powermeter = actor.has_powermeter
