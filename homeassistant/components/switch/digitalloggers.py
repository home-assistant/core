"""
Support for Digital Loggers DIN III Relays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.digitalloggers/
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

_LOGGER = logging.getLogger(__name__)


CONF_CYCLETIME = 'cycletime'

DEFAULT_NAME = 'DINRelay'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'
DEFAULT_TIMEOUT = 20
DEFAULT_CYCLETIME = 2

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

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
        hostname=host, userid=user, password=pswd,
        timeout=tout, cycletime=cycl
    )

    if not power_switch.verify():
        _LOGGER.error('Could not connect to DIN III Relay')
        return False

    devices = []
    parent_device = DINRelayDevice(power_switch)

    devices.extend(
        DINRelay(controllername, device.outlet_number, parent_device)
        for device in power_switch
    )

    add_devices(devices)


class DINRelay(SwitchDevice):
    """Representation of a individual DIN III relay port."""

    def __init__(self, name, outletnumber, parent_device):
        """Initialize the DIN III Relay switch."""
        self._parent_device = parent_device
        self.controllername = name
        self.outletnumber = outletnumber
        self.update()

    @property
    def name(self):
        """Return the display name of this relay."""
        return self._outletname

    @property
    def is_on(self):
        """Return true if relay is on."""
        return self._is_on

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def turn_on(self, **kwargs):
        """Instruct the relay to turn on."""
        self._parent_device.turn_on(outlet=self.outletnumber)

    def turn_off(self, **kwargs):
        """Instruct the relay to turn off."""
        self._parent_device.turn_off(outlet=self.outletnumber)

    def update(self):
        """Trigger update for all switches on the parent device."""
        self._parent_device.update()
        self._is_on = (
            self._parent_device.statuslocal[self.outletnumber - 1][2] == 'ON'
        )
        self._outletname = "{}_{}".format(
            self.controllername,
            self._parent_device.statuslocal[self.outletnumber - 1][1]
        )


class DINRelayDevice(object):
    """Device representation for per device throttling."""

    def __init__(self, device):
        """Initialize the DINRelay device."""
        self._device = device
        self.update()

    def turn_on(self, **kwargs):
        """Instruct the relay to turn on."""
        self._device.on(**kwargs)

    def turn_off(self, **kwargs):
        """Instruct the relay to turn off."""
        self._device.off(**kwargs)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for this device."""
        self.statuslocal = self._device.statuslist()
