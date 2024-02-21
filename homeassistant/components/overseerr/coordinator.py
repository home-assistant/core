"""Overseer coordinator s."""
from datetime import timedelta
import logging
from random import randrange
from typing import Self

from overseerr import ApiClient, Configuration, RequestApi
from overseerr.models import RequestCountGet200Response, RequestGet200Response

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Unable to connect to the web site."""


class OverseerrRequestData:
    """Keep data for Overseerr entities."""

    def __init__(self, api_client: ApiClient) -> None:
        """Initialise the weather entity data."""
        self.requests: RequestGet200Response | None = None
        self.request_count: RequestCountGet200Response | None = None
        self._api_client = api_client
        self._request_api = RequestApi(self._api_client)

    async def fetch_data(self) -> Self:
        """Fetch data from API - (current weather and forecast)."""
        self.requests = await self._request_api.request_get()
        self.request_count = await self._request_api.request_count_get()
        if not self.requests or not self.request_count:
            raise CannotConnect()
        return self


class OverseerrRequestUpdateCoordinator(DataUpdateCoordinator[OverseerrRequestData]):
    """Class to manage fetching Overseerr data."""

    def __init__(
        self, hass: HomeAssistant, configuration: Configuration, api_client: ApiClient
    ) -> None:
        """Initialize global Overseerr data updater."""
        self.hass = hass
        self._configuration = configuration
        self._api_client = api_client
        self.request_data = OverseerrRequestData(self._api_client)

        update_interval = timedelta(minutes=randrange(55, 65))

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> OverseerrRequestData:
        """Fetch data from Overseerr."""
        try:
            return await self.request_data.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
