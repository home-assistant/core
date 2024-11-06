"""Coordinator for Watergate API."""

from datetime import timedelta
import logging

from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import DeviceState

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WatergateDataCoordinator(DataUpdateCoordinator[DeviceState]):
    """Class to manage fetching watergate data."""

    def __init__(self, hass: HomeAssistant, api: WatergateLocalApiClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.api = api

    async def _async_update_data(self) -> DeviceState:
        try:
            state = await self.api.async_get_device_state()
        except WatergateApiException as exc:
            raise UpdateFailed from exc
        return state
