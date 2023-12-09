"""Tessie Data Coordinator."""
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from tessie_api import get_state

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import TessieStatus

# This matches the update interval Tessie performs server side
TESSIE_SYNC_INTERVAL = 10

_LOGGER = logging.getLogger(__name__)


class TessieDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tessie API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        vin: str,
        data: dict[str, Any],
    ) -> None:
        """Initialize Tessie Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tessie",
            update_method=self.async_update_data,
            update_interval=timedelta(seconds=TESSIE_SYNC_INTERVAL),
        )
        self.api_key = api_key
        self.vin = vin
        self.session = async_get_clientsession(hass)
        self.data = self._flattern(data)
        self.did_first_update = False

    async def async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Tessie API."""
        try:
            vehicle = await get_state(
                session=self.session,
                api_key=self.api_key,
                vin=self.vin,
                use_cache=self.did_first_update,
            )
        except ClientResponseError as e:
            if e.status == HTTPStatus.REQUEST_TIMEOUT:
                # Vehicle is offline, only update state and dont throw error
                self.data["state"] = TessieStatus.OFFLINE
                return self.data
            if e.status == HTTPStatus.UNAUTHORIZED:
                # Auth Token is no longer valid
                raise ConfigEntryAuthFailed from e
            raise e

        self.did_first_update = True
        if vehicle["state"] == TessieStatus.ONLINE:
            # Vehicle is online, all data is fresh
            return self._flattern(vehicle)

        # Vehicle is asleep, only update state
        self.data["state"] = vehicle["state"]
        return self.data

    def _flattern(
        self, data: dict[str, Any], parent: str | None = None
    ) -> dict[str, Any]:
        """Flattern the data structure."""
        result = {}
        for key, value in data.items():
            if parent:
                key = f"{parent}-{key}"
            if isinstance(value, dict):
                result.update(self._flattern(value, key))
            else:
                result[key] = value
        return result
