"""DataUpdateCoordinator for the London Air integration."""

import logging
from typing import override

from pylondonair import (
    LondonAirClient,
    LondonAirConnectionError,
    LondonAirData,
    LondonAirUpdateError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type LondonAirConfigEntry = ConfigEntry[LondonAirCoordinator]


class LondonAirCoordinator(DataUpdateCoordinator[LondonAirData]):
    """Define an object to hold London Air data."""

    config_entry: LondonAirConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LondonAirConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._client = LondonAirClient(session=async_get_clientsession(hass))

    @override
    async def _async_update_data(self) -> LondonAirData:
        """Fetch the latest data from the API."""
        try:
            return await self._client.async_update()
        except (LondonAirConnectionError, LondonAirUpdateError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error
