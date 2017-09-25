import logging

import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components import ads
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv
import pyads


_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'ADS Switch'
DEPENDENCIES = ['ads']

CONF_ADSVAR = 'adsvar'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    dev_name = config.get(CONF_NAME)
    ads_var = config.get(CONF_ADSVAR)
    add_devices([AdsSwitch(dev_name, ads_var)])


class AdsSwitch(ads.AdsDevice, ToggleEntity):
    """ Representation of an Ads switch device. """

    def __init__(self, dev_name, ads_var):
        ads.AdsDevice.__init__(self)
        self.dev_name = dev_name
        self.ads_var = ads_var
        self._on_state = False

    @property
    def is_on(self):
        return self._on_state

    @property
    def name(self):
        return self.dev_name

    def turn_on(self, **kwargs):
        self.write_by_name(self.ads_var, True, pyads.PLCTYPE_BOOL)
        self._on_state = True

    def turn_off(self, **kwargs):
        self.write_by_name(self.ads_var, False, pyads.PLCTYPE_BOOL)
        self._on_state = False

    def value_changed(self, val):
        self._on_state = val
        self.schedule_update_ha_state()
