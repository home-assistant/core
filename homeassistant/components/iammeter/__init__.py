"""Iammeter integration."""
from datetime import timedelta
import logging

from requests.exceptions import HTTPError, Timeout
from iammeter.client import IamMeter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for iammeter."""
    coordinator = IammeterData(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class IammeterData(update_coordinator.DataUpdateCoordinator):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name="Iammeter", update_interval=timedelta(seconds=60)
        )

        host_entry = entry.data[CONF_IP_ADDRESS]

        # url = urlparse(host_entry, "http")
        # netloc = url.netloc or url.path
        # path = url.path if url.netloc else ""
        # url = ParseResult("http", netloc, path, *url[3:])
        self.unique_id = entry.entry_id
        self.name = entry.title
        self.host = host_entry

    async def _async_update_data(self):
        """Update the data from the Iammeter device."""
        try:
            data = await self.hass.async_add_executor_job(IamMeter, self.host)
        except (OSError, Timeout, HTTPError) as err:
            raise update_coordinator.UpdateFailed(err)

        self.logger.debug(
            "Connection to Iammeter successful. Retrieving latest Iammeter from %s",
            data.serial_number,
        )

        return data
