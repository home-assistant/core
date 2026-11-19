"""Data update coordinator for Junker."""

from datetime import timedelta
import logging
from typing import override

from junker_api import Collection, JunkerClient, JunkerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_UPDATE_INTERVAL = timedelta(days=1)

type JunkerConfigEntry = ConfigEntry[JunkerDataUpdateCoordinator]


class JunkerDataUpdateCoordinator(DataUpdateCoordinator[list[Collection]]):
    """Fetch waste collection schedules from Junker."""

    config_entry: JunkerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: JunkerConfigEntry,
        client: JunkerClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=_UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> list[Collection]:
        """Fetch the current collection schedule."""
        try:
            return await self.client.async_get_collections()
        except JunkerError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
