"""Data Update coordinator for ZAMG weather data."""
from __future__ import annotations

from zamg import ZamgData as ZamgDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, MIN_TIME_BETWEEN_UPDATES


class ZamgDataUpdateCoordinator(DataUpdateCoordinator[ZamgDevice]):
    """Class to manage fetching ZAMG weather data."""

    config_entry: ConfigEntry
    data: dict = {}

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global ZAMG data updater."""
        self.zamg = ZamgDevice(session=async_get_clientsession(hass))

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self) -> ZamgDevice:
        """Fetch data from ZAMG api."""
        try:
            device = await self.zamg.update()
        except ValueError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
        self.data = device
        self.data["last_update"] = self.zamg.last_update
        return device
