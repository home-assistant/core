"""Solar-Log integration."""
from datetime import timedelta
import logging
from urllib.parse import ParseResult, urlparse

from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for solarlog."""
    coordinator = SolarlogData(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class SolarlogData(update_coordinator.DataUpdateCoordinator):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name="SolarLog", update_interval=timedelta(seconds=60)
        )

        host_entry = entry.data[CONF_HOST]

        url = urlparse(host_entry, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        self.unique_id = entry.entry_id
        self.name = entry.title
        self.host = url.geturl()

    async def _async_update_data(self):
        """Update the data from the SolarLog device."""
        try:
            data = await self.hass.async_add_executor_job(SolarLog, self.host)
        except (OSError, Timeout, HTTPError) as err:
            raise update_coordinator.UpdateFailed(err)

        if data.time.year == 1999:
            raise update_coordinator.UpdateFailed(
                "Invalid data returned (can happen after Solarlog restart)."
            )

        self.logger.debug(
            "Connection to Solarlog successful. Retrieving latest Solarlog update of %s",
            data.time,
        )

        return data
