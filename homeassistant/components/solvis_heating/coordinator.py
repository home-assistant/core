"""SolvisRemoteData integration."""
from datetime import timedelta
import logging

from sc2xmlreader.sc2xmlreader import SC2XMLReader

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

_LOGGER = logging.getLogger(__name__)


class SolvisRemoteCoordinator(update_coordinator.DataUpdateCoordinator):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            name="SolvisRemoteCoordinator",
            update_interval=timedelta(seconds=10),
        )

        host_entry = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        self.unique_id = entry.entry_id
        self.name = entry.title
        self.target_url = f"""http://{host_entry}"""
        self.manufacturer = "Solvis"
        self.model = "Solvis Max"

    async def _async_update_data(self):
        """Update the data from the SolvisRemote device."""
        try:
            data = await self.hass.async_add_executor_job(
                SC2XMLReader, self.target_url, self.username, self.password
            )
        except BaseException as err:
            raise update_coordinator.UpdateFailed(err)

        self.logger.debug(
            "Connection to SolvisRemote successful. Retrieving latest SolvisRemote data"
        )

        return data
