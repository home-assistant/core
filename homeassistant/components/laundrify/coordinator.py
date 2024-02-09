"""Custom DataUpdateCoordinator for the laundrify integration."""
import asyncio
from datetime import timedelta
import logging

from laundrify_aio import LaundrifyAPI
from laundrify_aio.exceptions import ApiConnectionException, UnauthorizedException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, REQUEST_TIMEOUT
from .model import LaundrifyDevice

_LOGGER = logging.getLogger(__name__)


class LaundrifyUpdateCoordinator(DataUpdateCoordinator[dict[str, LaundrifyDevice]]):
    """Class to manage fetching laundrify API data."""

    def __init__(
        self, hass: HomeAssistant, laundrify_api: LaundrifyAPI, poll_interval: int
    ) -> None:
        """Initialize laundrify coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.laundrify_api = laundrify_api

    async def _async_update_data(self) -> dict[str, LaundrifyDevice]:
        """Fetch data from laundrify API."""
        try:
            # Note: TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(REQUEST_TIMEOUT):
                return {m["_id"]: m for m in await self.laundrify_api.get_machines()}
        except UnauthorizedException as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiConnectionException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
