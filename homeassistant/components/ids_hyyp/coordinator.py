"""Provides the ezviz DataUpdateCoordinator."""
from datetime import timedelta
import logging
from typing import Any

from async_timeout import timeout
from pyhyypapi.client import HyypClient
from pyhyypapi.exceptions import HTTPError, HyypApiError, InvalidURL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HyypDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching IDSHyyp data."""

    def __init__(
        self, hass: HomeAssistant, *, api: HyypClient, api_timeout: int
    ) -> None:
        """Initialize global IDS Hyyp data updater."""
        self.hyyp_client = api
        self._api_timeout = api_timeout
        update_interval = timedelta(seconds=60)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[Any, Any]:
        """Fetch data from IDS Hyyp."""
        try:
            async with timeout(self._api_timeout):
                return await self.hass.async_add_executor_job(
                    self.hyyp_client.load_alarm_infos
                )

        except (InvalidURL, HTTPError, HyypApiError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
