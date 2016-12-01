"""
Support for Digital Loggers DIN III Relays and possibly other items through
Dwight Hubbard's, python-dlipower.

For more details about python-dlipower, please see
https://github.com/dwighthubbard/python-dlipower
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle


REQUIREMENTS = ['dlipower==0.7.165']

CONF_CYCLETIME = 'cycletime'

DEFAULT_NAME = 'DINRelay'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'
DEFAULT_TIMEOUT = 20
DEFAULT_CYCLETIME = 3

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
    vol.Optional(CONF_CYCLETIME, default=DEFAULT_CYCLETIME):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),

})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return DIN III Relay switch."""
    import dlipower

    host = config.get(CONF_HOST)
    controllername = config.get(CONF_NAME)
    user = config.get(CONF_USERNAME)
    pswd = config.get(CONF_PASSWORD)
    tout = config.get(CONF_TIMEOUT)
    cycl = config.get(CONF_CYCLETIME)

    power_switch = dlipower.PowerSwitch(
        hostname=host, userid=user, password=pswd, timeout=tout,
        cycletime=cycl)

    if not power_switch.verify():
        _LOGGER.error('Could not connect to DIN III Relay')
        return False

    for switch in power_switch:

        # TODO(dethpickle)  Throttle the update for all relays of one
        # physical device using util.Throttle.

        add_devices(
            [DINRelay(controllername, host, switch.outlet_number,
                      power_switch)]
        )


class DINRelay(SwitchDevice):

    """Representation of a DIN III Relay switch."""

    def __init__(self, name, host, outletnumber, switchref):
        """Initialize the DIN III Relay switch."""
        self._host = host
        self.controllername = name
        self.outletnumber = outletnumber
        self.switchref = switchref
        self.update()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._outletname

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the light to turn on.        """
        self.switchref.on(outlet=self.outletnumber)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.switchref.off(outlet=self.outletnumber)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.switchref.status(outlet=self.outletnumber)
        self._is_on = (self.switchref.status(outlet=self.outletnumber) == 'ON')
        self._outletname = "{}_{}".format(self.controllername,
                                          self.switchref.get_outlet_name(
                                            outlet=self.outletnumber))
