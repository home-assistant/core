"""Polling coordinator for the Sensoterra integration.

https://developers.home-assistant.io/docs/integration_fetching_data/#coordinated-single-api-poll-for-data-for-all-entities
"""

from datetime import timedelta
import logging

# import async_timeout
from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as ApiAuthError,
    Timeout as ApiTimeout,
)

# from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant  # callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    # CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SensoterraCoordinator(DataUpdateCoordinator):
    """Sensoterra coordinator."""

    def __init__(self, hass: HomeAssistant, api: CustomerApi) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Sensoterra probe",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # # handled by the data update coordinator.
            # async with async_timeout.timeout(10):
            #     # Grab active context variables to limit data required to be fetched from API
            #     # Note: using context is not required if there is no need or ability to limit
            #     # data retrieved from API.
            #     listening_idx = set(self.async_contexts())
            #     return await self.api.fetch_data(listening_idx)
            return await self.api.poll()
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiTimeout as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
