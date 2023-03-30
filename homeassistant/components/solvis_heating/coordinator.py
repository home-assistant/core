"""SolvisRemoteData integration."""
from datetime import timedelta
import logging

from sc2xmlreader.sc2xmlreader import SC2XMLReader

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import (
    CONF_OPTION_OVEN,
    CONF_OPTION_SOLAR,
    CONF_OPTION_SOLAR_EAST_WEST,
    CONF_OPTION_WARMWATER_STATION,
    CONF_UPDATE_TIMESPAN,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DOMAIN,
)

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

        entry.async_on_unload(entry.add_update_listener(update_listener))
        host_entry = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        self.warmwater_station = entry.data[CONF_OPTION_WARMWATER_STATION]
        self.solar = entry.data[CONF_OPTION_SOLAR]
        self.solar_east_west = entry.data[CONF_OPTION_SOLAR_EAST_WEST]
        self.oven = entry.data[CONF_OPTION_OVEN]

        update_ = entry.data[CONF_UPDATE_TIMESPAN]
        if 10 >= update_ <= 300:
            self.update_interval = timedelta(seconds=update_)

        self.unique_id = entry.entry_id
        self.name = entry.title
        self.target_url = f"""http://{host_entry}"""
        self.manufacturer = DEFAULT_MANUFACTURER
        self.model = DEFAULT_MODEL

    async def _async_update_data(self):
        """Update the data from the SolvisRemote device."""
        try:
            data = await self.hass.async_add_executor_job(
                SC2XMLReader,
                self.target_url,
                self.username,
                self.password,
                self.warmwater_station,
                self.solar,
                self.solar_east_west,
                self.oven,
            )
        except BaseException as err:
            raise update_coordinator.UpdateFailed(err)

        return data


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    update_ = entry.data[CONF_UPDATE_TIMESPAN]
    if 10 >= update_ <= 300:
        coordinator.update_interval = timedelta(seconds=update_)
