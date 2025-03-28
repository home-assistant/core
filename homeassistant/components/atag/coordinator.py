"""The ATAG Integration."""

from asyncio import timeout
from datetime import timedelta
import logging

from pyatag import AtagException, AtagOne

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type AtagConfigEntry = ConfigEntry[AtagDataUpdateCoordinator]


class AtagDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Atag data update coordinator."""

    config_entry: AtagConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: AtagConfigEntry) -> None:
        """Initialize Atag coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Atag",
            update_interval=timedelta(seconds=60),
        )

        self.atag = AtagOne(
            session=async_get_clientsession(hass),
            **config_entry.data,
            device=config_entry.unique_id,
        )

    async def _async_update_data(self) -> None:
        """Update data via library."""
        async with timeout(20):
            try:
                await self.atag.update()
            except AtagException as err:
                raise UpdateFailed(err) from err
