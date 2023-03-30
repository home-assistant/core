"""SolvisRemoteData integration."""
from datetime import timedelta
import logging
from urllib.parse import ParseResult, urlparse

from requests.exceptions import HTTPError, Timeout
from sc2xmlreader.sc2xmlreader import SC2XMLReader

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

_LOGGER = logging.getLogger(__name__)


class SolvisRemoteData(update_coordinator.DataUpdateCoordinator):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name="SolvisRemote", update_interval=timedelta(seconds=10)
        )

        host_entry = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        url = urlparse(host_entry, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        self.unique_id = entry.entry_id
        self.name = entry.title
        self.host = url.geturl()

    async def _async_update_data(self):
        """Update the data from the SolvisRemote device."""
        try:
            data = await self.hass.async_add_executor_job(
                SC2XMLReader, self.host, self.username, self.password
            )
        except (OSError, Timeout, HTTPError) as err:
            raise update_coordinator.UpdateFailed(err)

        self.logger.debug(
            "Connection to SolvisRemote successful. Retrieving latest SolvisRemote data"
        )

        return data
