"""Support for APCUPSd via its Network Information Server (NIS)."""
import logging

from apcaccess import status
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3551
DEFAULT_POLL_INTERVAL = 60
DOMAIN = "apcupsd"

KEY_STATUS = "STATFLAG"

VALUE_ONLINE = 8

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): cv.time_period_seconds,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Use config values to set up a function enabling status retrieval."""
    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    poll_time = conf[CONF_POLL_INTERVAL]

    apcups_data = APCUPSdData(host, port, poll_time)
    hass.data[DOMAIN] = apcups_data

    # It doesn't really matter why we're not able to get the status, just that
    # we can't.
    try:
        apcups_data.update(no_throttle=True)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failure while testing APCUPSd status retrieval.")
        return False
    return True


class APCUPSdData:
    """Stores the data retrieved from APCUPSd.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port, poll_time):
        """Initialize the data object."""

        self._host = host
        self._port = port
        self._status = None
        self._get = status.get
        self._parse = status.parse
        self.update = Throttle(poll_time)(self._update)

    @property
    def status(self):
        """Get latest update if throttle allows. Return status."""
        self.update()
        return self._status

    def _get_status(self):
        """Get the status from APCUPSd and parse it into a dict."""
        return self._parse(self._get(host=self._host, port=self._port))

    def _update(self, **kwargs):
        """Fetch the latest status from APCUPSd."""
        self._status = self._get_status()
