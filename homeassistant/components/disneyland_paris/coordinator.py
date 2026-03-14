"""DataUpdateCoordinator for Disneyland Paris Integration."""

from datetime import timedelta
import logging
from typing import Final

from dlpwait import DLPWaitAPI, DLPWaitError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(minutes=5)

type DisneylandParisConfigEntry = ConfigEntry[DisneylandParisCoordinator]


class DisneylandParisCoordinator(DataUpdateCoordinator[None]):
    """Disneyland Paris Device Coordinator Class."""

    def __init__(self, hass: HomeAssistant, entry: DisneylandParisConfigEntry) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Disneyland Paris",
            update_interval=SCAN_INTERVAL,
        )
        self.client = DLPWaitAPI(async_get_clientsession(hass))

    async def _async_update_data(self) -> None:
        """Fetch the latest parks data."""

        try:
            await self.client.update()
        except DLPWaitError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error
