"""The Unmanic integration."""
from datetime import timedelta
import logging
from typing import List

from unmanic_api import Unmanic, UnmanicError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    __version__,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = Unmanic(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        request_timeout=entry.data[CONF_TIMEOUT],
        session=session,
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        user_agent=f"HomeAssistant/Unmanic/{__version__}",
    )

    coordinator = UnmanicUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class UnmanicUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: Unmanic) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []  # type: List[str]

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            data = {}
            data["pending_tasks"] = await self.api.get_pending_tasks()
            data["settings"] = await self.api.get_settings()
            data["task_history"] = await self.api.get_task_history()
            data["version"] = await self.api.get_version()
            data["workers_status"] = await self.api.get_workers_status()
            return data
        except UnmanicError as exception:
            raise UpdateFailed() from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
