"""Define an object to coordinate fetching Ondilo ICO data."""

from datetime import timedelta
import logging
from typing import Any

from ondilo import OndiloError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import DOMAIN
from .api import OndiloClient

_LOGGER = logging.getLogger(__name__)


class OndiloIcoCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching Ondilo ICO data from API."""

    def __init__(self, hass: HomeAssistant, api: OndiloClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.api = api

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API endpoint."""
        try:
            return await self.hass.async_add_executor_job(self.api.get_all_pools_data)

        except OndiloError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
