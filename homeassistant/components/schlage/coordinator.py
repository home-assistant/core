"""DataUpdateCoordinator for the Schlage integration."""
from __future__ import annotations

from dataclasses import dataclass

from pyschlage import Lock, Schlage
from pyschlage.exceptions import Error

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


@dataclass
class SchlageData:
    """Container for cached data from the Schlage API."""

    locks: dict[str, Lock]


class SchlageDataUpdateCoordinator(DataUpdateCoordinator[SchlageData]):
    """The Schlage data update coordinator."""

    def __init__(self, hass: HomeAssistant, username: str, api: Schlage) -> None:
        """Initialize the class."""
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN} ({username})", update_interval=UPDATE_INTERVAL
        )
        self.api = api

    async def _async_update_data(self) -> SchlageData:
        """Fetch the latest data from the Schlage API."""
        try:
            return await self.hass.async_add_executor_job(self._update_data)
        except Error as ex:
            raise UpdateFailed("Failed to refresh Schlage data") from ex

    def _update_data(self) -> SchlageData:
        """Fetch the latest data from the Schlage API."""
        return SchlageData(locks={lock.device_id: lock for lock in self.api.locks()})
