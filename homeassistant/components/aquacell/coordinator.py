"""Coordinator to update data from Aquacell API."""
from datetime import timedelta
import logging

from aioaquacell import AquacellApi, AquacellApiException, Softener
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class Coordinator(DataUpdateCoordinator[list[Softener]]):
    """My custom coordinator."""

    def __init__(
        self, hass: HomeAssistant, aquacell_api: AquacellApi, refresh_token: str
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=3600),
        )
        self.aquacell_api = aquacell_api
        self.refresh_token = refresh_token

    async def _async_update_data(self) -> list[Softener]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                _LOGGER.debug("Logging in using: %s", self.refresh_token)
                await self.aquacell_api.authenticate_refresh(self.refresh_token)
                _LOGGER.debug("Logged in")
                return await self.aquacell_api.get_all_softeners()
        # except  as err:
        # Raising ConfigEntryAuthFailed will cancel future updates
        # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #    raise ConfigEntryAuthFailed from err
        except AquacellApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
