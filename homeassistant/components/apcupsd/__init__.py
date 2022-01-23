"""Support for APCUPSd via its Network Information Server (NIS)."""
from datetime import timedelta
import logging
from typing import Final

from apcaccess import status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "apcupsd"
KEY_STATUS: Final = "STATFLAG"
VALUE_ONLINE: Final = 8
PLATFORMS: Final = (Platform.SENSOR, Platform.BINARY_SENSOR)
MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Use config values to set up a function enabling status retrieval."""
    data_service = APCUPSdData(
        config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
    )

    # It doesn't really matter why we're not able to get the status, just that we can't.
    try:
        data_service.update(no_throttle=True)
    except Exception:
        _LOGGER.exception("Failure while testing APCUPSd status retrieval")
        return False

    # Set up option update handler.
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_options_updated)
    )

    # Store the data service object.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = data_service

    # Forward the config entries to the supported platforms.
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


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
        self.update()
        return self._status

    def _get_status(self):
        """Get the status from APCUPSd and parse it into a dict."""
        return self._parse(self._get(host=self._host, port=self._port))

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Fetch the latest status from APCUPSd."""
        self._status = self._get_status()
