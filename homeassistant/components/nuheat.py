"""
Support for NuHeat thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/nuheat/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ["nuheat==0.2.0"]

_LOGGER = logging.getLogger(__name__)

DATA_NUHEAT = "nuheat"

DOMAIN = "nuheat"

CONF_MIN_AWAY_TEMP = 'min_away_temp'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DEVICES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_MIN_AWAY_TEMP): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the NuHeat thermostat component."""
    import nuheat

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    devices = conf.get(CONF_DEVICES)

    min_away_temp = None
    _min_away_temp = conf.get(CONF_MIN_AWAY_TEMP)
    if _min_away_temp:
        try:
            min_away_temp = int(_min_away_temp)
        except ValueError:
            _LOGGER.error(
                "Configuration error. %s.%s=%s is invalid. Please provide a "
                "numeric value.", DATA_NUHEAT, CONF_MIN_AWAY_TEMP, _min_away_temp)

    api = nuheat.NuHeat(username, password)
    api.authenticate()
    hass.data[DATA_NUHEAT] = (api, devices, min_away_temp)

    discovery.load_platform(hass, "climate", DOMAIN, {}, config)
    _LOGGER.debug("NuHeat initialized")
    return True
