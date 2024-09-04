"""DataUpdateCoordinator for the SABnzbd integration."""

from datetime import timedelta
import logging
from typing import Any

from pysabnzbd import SabnzbdApi, SabnzbdApiException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class SabnzbdUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The SABnzbd update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        sab_api: SabnzbdApi,
    ) -> None:
        """Initialize the SABnzbd update coordinator."""
        self.sab_api = sab_api

        super().__init__(
            hass,
            _LOGGER,
            name="SABnzbd",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest data from the SABnzbd API."""
        try:
            await self.sab_api.refresh_data()
        except SabnzbdApiException as err:
            raise UpdateFailed("Error while fetching data") from err

        return self.sab_api.queue
