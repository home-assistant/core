"""DataUpdateCoordinator for Kiosker."""

from __future__ import annotations

from datetime import timedelta
import logging

from kiosker import KioskerAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class KioskerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Kiosker API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: KioskerAPI,
        poll_interval: int,
    ) -> None:
        """Initialize."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        try:
            status = await self.hass.async_add_executor_job(self.api.status)
            blackout = await self.hass.async_add_executor_job(self.api.blackout_get)
            screensaver = await self.hass.async_add_executor_job(
                self.api.screensaver_get_state
            )
        except Exception as exception:
            _LOGGER.warning(
                "Failed to update Kiosker data: %s", exception, exc_info=True
            )
            raise UpdateFailed(exception) from exception
        else:
            return {
                "status": status,
                "blackout": blackout,
                "screensaver": screensaver,
            }
