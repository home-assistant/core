"""Overseer coordinator s."""
from datetime import timedelta
import logging
from typing import Self

from overseerr_api import ApiClient, RequestApi
from overseerr_api.models import RequestCountGet200Response

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Unable to connect to the web site."""


class OverseerrRequestData:
    """Keep data for Overseerr entities."""

    def __init__(self, api_client: ApiClient, hass: HomeAssistant) -> None:
        """Initialise the request entity data."""
        self.request_count: RequestCountGet200Response = RequestCountGet200Response()
        self._api_client = api_client
        self.hass = hass
        self._request_api = RequestApi(self._api_client)

    async def fetch_data(self) -> Self:
        """Fetch data from API."""
        self.request_count = await self.hass.async_add_executor_job(
            self._request_api.request_count_get
        )

        if not self.request_count:
            raise CannotConnect()
        return self


class OverseerrUpdateCoordinator(DataUpdateCoordinator[OverseerrRequestData]):
    """Class to manage fetching Overseerr data."""

    def __init__(self, hass: HomeAssistant, api_client: ApiClient) -> None:
        """Initialize global Overseerr data updater."""
        self.overseerr_client = OverseerrRequestData(api_client, hass)
        self._api_client = api_client
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5)
        )

    async def _async_update_data(self) -> OverseerrRequestData:
        """Fetch data from Overseerr."""
        try:
            return await self.overseerr_client.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
