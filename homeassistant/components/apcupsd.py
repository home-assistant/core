"""
Support for status output of APCUPSd via its Network Information Server (NIS).

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/apcupsd/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['apcaccess==0.0.10']

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = 'type'

DATA = None
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 3551
DOMAIN = 'apcupsd'

KEY_STATUS = 'STATUS'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

VALUE_ONLINE = 'ONLINE'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Use config values to set up a function enabling status retrieval."""
    global DATA
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)

    DATA = APCUPSdData(host, port)

    # It doesn't really matter why we're not able to get the status, just that
    # we can't.
    # pylint: disable=broad-except
    try:
        DATA.update(no_throttle=True)
    except Exception:
        _LOGGER.exception("Failure while testing APCUPSd status retrieval.")
        return False
    return True


class APCUPSdData(object):
    """Stores the data retrieved from APCUPSd.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port):
        """Initialize the data oject."""
        from apcaccess import status
        self._host = host
        self._port = port
        self._status = None
        self._get = status.get
        self._parse = status.parse

    @property
    def status(self):
        """Get latest update if throttle allows. Return status."""
        self.update()
        return self._status

    def _get_status(self):
        """Get the status from APCUPSd and parse it into a dict."""
        return self._parse(self._get(host=self._host, port=self._port))

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Fetch the latest status from APCUPSd."""
        self._status = self._get_status()
