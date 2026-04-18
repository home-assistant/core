"""Meater Coordinator."""

import asyncio
from datetime import timedelta
import logging

from meater.MeaterApi import (
    AuthenticationError,
    MeaterApi,
    MeaterProbe,
    ServiceUnavailableError,
    TooManyRequestsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type MeaterConfigEntry = ConfigEntry[MeaterCoordinator]


class MeaterCoordinator(DataUpdateCoordinator[dict[str, MeaterProbe]]):
    """Meater Coordinator."""

    config_entry: MeaterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MeaterConfigEntry,
    ) -> None:
        """Initialize the Meater Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Meater {entry.title}",
            update_interval=timedelta(seconds=30),
        )
        session = async_get_clientsession(hass)
        self.client = MeaterApi(session)
        self.found_probes: set[str] = set()

    async def _async_setup(self) -> None:
        """Set up the Meater Coordinator."""
        try:
            _LOGGER.debug("Authenticating with the Meater API")
            await self.client.authenticate(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
        except (ServiceUnavailableError, TooManyRequestsError) as err:
            raise UpdateFailed from err
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Unable to authenticate with the Meater API: {err}"
            ) from err

    async def _async_update_data(self) -> dict[str, MeaterProbe]:
        """Fetch data from API endpoint."""
        try:
            # Note: TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
                devices: list[MeaterProbe] = await self.client.get_all_devices()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("The API call wasn't authenticated") from err
        except TooManyRequestsError as err:
            raise UpdateFailed(
                "Too many requests have been made to the API, rate limiting is in place"
            ) from err
        res = {device.id: device for device in devices}
        self.found_probes.update(set(res.keys()))
        return res
