"""Overseer coordinator s."""
import asyncio
from datetime import timedelta
import logging

from overseerr.exceptions import OpenApiException, UnauthorizedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class OverseerrCoordinator(DataUpdateCoordinator):
    """Overseerr update coordinator."""

    config_entry: ConfigEntry
    update_interval = timedelta(minutes=1)

    def __init__(self, hass: HomeAssistant, api_client, configuration) -> None:
        """Initialize overseerr coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Overseerr sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.configuration = configuration
        self.api_client = api_client

        async def _async_update_data(self):
            """Fetch data from API endpoint.

            This is the place to pre-process the data to lookup tables
            so entities can quickly look up their data.
            """
            try:
                # Note: asyncio.TimeoutError and aiohttp.ClientError are already
                # handled by the data update coordinator.
                async with asyncio.timeout(10):
                    # Grab active context variables to limit data required to be fetched from API
                    # Note: using context is not required if there is no need or ability to limit
                    # data retrieved from API.

                    listening_idx = set(self.async_contexts())
                    return await self.my_api.fetch_data(listening_idx)
            except UnauthorizedException as err:
                # Raising ConfigEntryAuthFailed will cancel future updates
                # and start a config flow with SOURCE_REAUTH (async_step_reauth)
                raise ConfigEntryAuthFailed from err
            except OpenApiException as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err
