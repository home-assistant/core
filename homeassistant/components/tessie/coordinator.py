"""Tessie Data Coordinator."""
from datetime import timedelta
from http import HTTPStatus
import logging

from aiohttp import ClientResponseError, ClientSession
from tessie_api import get_state_of_all_vehicles

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

TESSIE_SYNC_INTERVAL = 15

_LOGGER = logging.getLogger(__name__)


class TessieDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tessie API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
    ) -> None:
        """Initialize Tessie Data Update Coordinator."""
        self.api_key: str = api_key
        self.session: ClientSession = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name="Tessie",
            update_method=self.async_update_data,
            update_interval=timedelta(seconds=TESSIE_SYNC_INTERVAL),
        )

    async def async_update_data(self) -> dict[str, dict[str, dict[str, str]]]:
        """Update data using Tessie API."""
        try:
            vehicles = await get_state_of_all_vehicles(
                session=self.session, api_key=self.api_key, only_active=True
            )
        except ClientResponseError as e:
            if e.status == HTTPStatus.UNAUTHORIZED:
                raise ConfigEntryAuthFailed from e
            raise e
        return {
            vehicle["vin"]: vehicle["last_state"] for vehicle in vehicles["results"]
        }
