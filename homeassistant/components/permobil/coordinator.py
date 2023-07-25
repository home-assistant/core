"""DataUpdateCoordinator for permobil integration."""

from datetime import timedelta
import logging

import async_timeout
from mypermobil import (
    ENDPOINT_BATTERY_INFO,
    ENDPOINT_DAILY_USAGE,
    ENDPOINT_VA_USAGE_RECORDS,
    MyPermobil,
    MyPermobilAPIException,
    MyPermobilClientException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


class MyPermobilCoordinator(DataUpdateCoordinator):
    """MyPermobil coordinator."""

    def __init__(self, hass: HomeAssistant, p_api: MyPermobil) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="permobil",
            update_interval=timedelta(seconds=50),
        )
        self.p_api = p_api

    async def _async_update_data(self):
        """Fetch data from the 3 API endpoints."""
        try:
            async with async_timeout.timeout(10):
                data = {
                    ENDPOINT_BATTERY_INFO: None,
                    ENDPOINT_DAILY_USAGE: None,
                    ENDPOINT_VA_USAGE_RECORDS: None,
                }
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                for endpoint in data:
                    data[endpoint] = await self.p_api.request_endpoint(endpoint)
                return data
        except MyPermobilClientException as err:
            raise ConfigEntryAuthFailed from err
        except MyPermobilAPIException as err:
            raise UpdateFailed from err
