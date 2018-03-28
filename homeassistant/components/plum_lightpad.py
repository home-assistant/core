"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import discovery

REQUIREMENTS = ['plumlightpad==0.0.8']

DOMAIN = 'plum_lightpad'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Plum Lightpad component."""
    from plumlightpad import Plum

    conf = config[DOMAIN]
    # print("****************************************************************")
    # print(conf.get(CONF_USERNAME))
    # print("****************************************************************")
    plum = Plum(conf.get(CONF_USERNAME), conf.get(CONF_PASSWORD))
    hass.data['plum'] = plum

    discovery.load_platform(hass, 'light', DOMAIN, None, conf)
    return True