"""Coordinator for Lichess."""

from datetime import timedelta
import logging

from aiolichess import AioLichess
from aiolichess.exceptions import AioLichessError
from aiolichess.models import LichessStatistics

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type LichessConfigEntry = ConfigEntry[LichessCoordinator]


class LichessCoordinator(DataUpdateCoordinator[LichessStatistics]):
    """Coordinator for Lichess."""

    config_entry: LichessConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: LichessConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(hours=1),
        )
        self.client = AioLichess(session=async_get_clientsession(hass))

    async def _async_update_data(self) -> LichessStatistics:
        """Update data for Lichess."""
        try:
            return await self.client.get_statistics(
                token=self.config_entry.data[CONF_API_TOKEN]
            )
        except AioLichessError as err:
            raise UpdateFailed("Error in communicating with Lichess") from err
