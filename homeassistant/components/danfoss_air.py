"""
Support for Danfoss Air HRV.

Configuration: 
    danfoss_air:
        host: IP_OF_CCM_MODULE

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/danfoss_air/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['pydanfossair==0.0.4']

_LOGGER = logging.getLogger(__name__)

DANFOSS_AIR_PLATFORMS = ['sensor', 'binary_sensor']
DOMAIN = 'danfoss_air'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """Set up the Danfoss Air component."""
    conf = config[DOMAIN]
    
    danfoss_config = {}
    danfoss_config['host'] = conf[CONF_HOST]

    hass.data['DANFOSS_DO'] = DanfossAir(danfoss_config)

    for platform in DANFOSS_AIR_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True

class DanfossAir(object):
    """Handle all communication with Danfoss Air CCM unit."""

    def __init__(self, host):
        """Initialize the Danfoss Air CCM connection."""

        self._data = {}

        from pydanfossair.danfossclient import DanfossClient
        self._client = DanfossClient(host)

    def getValue(self, item):
        if item in self._data:
            return self._data[item]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Digital Ocean API."""
        _LOGGER.debug("Fetching data from Danfoss Air CCM module")
        from pydanfossair.commands import ReadCommand
        self._data["EXHAUST_TEMPERATURE"] = self._client.command(ReadCommand.exhaustTemperature)
        self._data["OUTDOOR_TEMPERATURE"] = self._client.command(ReadCommand.outdoorTemperature)
        self._data["SUPPLY_TEMPERATURE"] = self._client.command(ReadCommand.supplyTemperature)
        self._data["EXTRACT_TEMPERATURE"] = self._client.command(ReadCommand.extractTemperature)
        self._data["HUMIDITY_PERCENT"] = round(self._client.command(ReadCommand.humidity), 2)
        self._data["FILTER_PERCENT"] = round(self._client.command(ReadCommand.filterPercent), 2)
        self._data["BYPASS_ACTIVE"] = self._client.command(ReadCommand.bypass)

        _LOGGER.debug("Done fetching data from Danfoss Air CCM module")
