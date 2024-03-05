"""Overseer coordinator s."""
from datetime import timedelta
import logging

from overseerr_api import ApiClient, Configuration, RequestApi
from overseerr_api.exceptions import OpenApiException
from overseerr_api.models import RequestCountGet200Response
from urllib3.exceptions import MaxRetryError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OverseerrUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Overseerr data."""

    def __init__(self, hass: HomeAssistant, overseerr_config: Configuration) -> None:
        """Initialize global Overseerr data updater."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5)
        )
        self._api_client = ApiClient(overseerr_config)
        self._request_api = RequestApi(self._api_client)
        self.request_count: RequestCountGet200Response = RequestCountGet200Response()

    async def _async_update_data(self):
        """Fetch data from Overseerr."""
        try:
            self.request_count = await self.hass.async_add_executor_job(
                self._request_api.request_count_get
            )
        except (OpenApiException, MaxRetryError) as err:
            raise UpdateFailed(f"Update failed: {err}") from err
