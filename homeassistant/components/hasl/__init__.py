"""HomeAssistant Sensor for SL (Storstockholms Lokaltrafik)"""
import datetime
import json
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import now

__version__ = '2.1.0'
_LOGGER = logging.getLogger(__name__)

DOMAIN = "hasl"
VERSION = __version__


def setup(hass, config):
    """Setup our communication platform."""

    def clear_cache(call):
        for sensor in hass.data[DOMAIN]:
                hass.data[DOMAIN][sensor] = ''

        jsonFile = open(hass.config.path('haslcache.json'), "w")
        jsonFile.write(json.dumps({}))
        jsonFile.close()

        return "{ 'result': true }"

    # track_time_interval(hass, FUNC, INTERVALL).
    hass.services.register(DOMAIN, 'clear_cache', clear_cache)

    # Return boolean to indicate that initialization was successfully.
    return True
