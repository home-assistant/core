import voluptuous as vol
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_ID)
import homeassistant.helpers.config_validation as cv
from . import pytuya

DEFAULT_ID = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ID, default=DEFAULT_ID): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):

    add_devices([tuya(
        config.get(CONF_NAME),
        config.get(CONF_HOST),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_ID)
    )])

class tuya(SwitchDevice):

    def __init__(self, name, host, devid, localkey, switchid):
        self._name = name
        self._state = False
        self._switchid = switchid
        self._localkey = localkey
        self._devid = devid
        self._host = host

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    def turn_on(self, **kwargs):
        d = pytuya.OutletDevice(self._devid, self._host, self._localkey)
        d.set_status(True, self._switchid)
        self._state = True
        self.async_schedule_update_ha_state()

    def turn_off(self, **kwargs):
        d = pytuya.OutletDevice(self._devid, self._host, self._localkey)
        d.set_status(False, self._switchid)
        self._state = False
        self.async_schedule_update_ha_state()
