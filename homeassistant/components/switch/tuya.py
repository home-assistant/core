"""
Simple platform to control **SOME** Tuya devices.

It uses a slightly modified version of the pytuya library
(https://github.com/clach04/python-tuya) to directly control the device.

Most devices that use the Tuya cloud should work. If port 6668 is open on
the device then it will work.
"""
import voluptuous as vol
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_ID)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pytuya==1.0']

CONF_DEVID = 'device_id'
CONF_LOCKEY = 'local_key'

DEFAULT_ID = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVID): cv.string,
    vol.Required(CONF_LOCKEY): cv.string,
    vol.Optional(CONF_ID, default=DEFAULT_ID): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Tuya switch."""
    import pytuya

    add_devices([tuya(
        pytuya,
        config.get(CONF_NAME),
        config.get(CONF_HOST),
        config.get(CONF_DEVID),
        config.get(CONF_LOCKEY),
        config.get(CONF_ID)
    )])


class tuya(SwitchDevice):
    """Representation of a Tuya switch."""

    def __init__(self, pytuy, name, host, devid, localkey, switchid):
        """Initialize the Tuya switch."""
        self._pytuy = pytuy
        self._name = name
        self._state = False
        self._switchid = switchid
        self._localkey = localkey
        self._devid = devid
        self._host = host

    @property
    def name(self):
        """Get name of Tuya switch."""
        return self._name

    @property
    def is_on(self):
        """Check if Tuya switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn Tuya switch on."""
        d = self._pytuy.OutletDevice(self._devid, self._host, self._localkey)
        d.set_status(True, self._switchid)
        self._state = True
        self.async_schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn Tuya switch off."""
        d = self._pytuy.OutletDevice(self._devid, self._host, self._localkey)
        d.set_status(False, self._switchid)
        self._state = False
        self.async_schedule_update_ha_state()
