"""Support for APCUPSd via its Network Information Server (NIS)."""
from datetime import timedelta
import logging

from apcaccess import status
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3551
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
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
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.time_period, cv.positive_timedelta),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Use config values to set up a function enabling status retrieval."""
    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    apcups_data = APCUPSdData(host, port)
    hass.data[DOMAIN] = apcups_data

    # It doesn't really matter why we're not able to get the status, just that
    # we can't.
    try:
        await apcups_data._update_status()
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failure while testing APCUPSd status retrieval")
        return True

    async def update_status_callback(now):
        # It doesn't really matter why we're not able to get the status, just that
        # we can't.
        try:
            await apcups_data._update_status()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Failure while testing APCUPSd status retrieval")
            return True

    hass.helpers.event.async_track_time_interval(update_status_callback, scan_interval)

    return True


class APCUPSdData:
    """Stores the data retrieved from APCUPSd.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port):
        """Initialize the data object."""

        self._host = host
        self._port = port
        self._status = None
        self._get = status.get
        self._parse = status.parse

    @property
    def status(self):
        """Get latest update if throttle allows. Return status."""
        return self._status

    def _get_status(self):
        """Get the status from APCUPSd and parse it into a dict."""
        return self._parse(self._get(host=self._host, port=self._port))

    async def _update_status(self, **kwargs):
        """Fetch the latest status from APCUPSd."""
        self._status = self._get_status()
