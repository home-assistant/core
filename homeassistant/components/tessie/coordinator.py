"""Tessie Data Coordinator."""

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from tessie_api import get_state, get_status

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import TessieStatus

# This matches the update interval Tessie performs server side
TESSIE_SYNC_INTERVAL = 10

_LOGGER = logging.getLogger(__name__)


class TessieStateUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
            update_interval=timedelta(seconds=TESSIE_SYNC_INTERVAL),
        )
        self.api_key = api_key
        self.vin = vin
        self.session = async_get_clientsession(hass)
        self.data = self._flatten(data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Tessie API."""
        try:
            status = await get_status(
                session=self.session,
                api_key=self.api_key,
                vin=self.vin,
            )
            if status["status"] == TessieStatus.ASLEEP:
                # Vehicle is asleep, no need to poll for data
                self.data["state"] = status["status"]
                return self.data

            vehicle = await get_state(
                session=self.session,
                api_key=self.api_key,
                vin=self.vin,
                use_cache=True,
            )
        except ClientResponseError as e:
            if e.status == HTTPStatus.UNAUTHORIZED:
                # Auth Token is no longer valid
                raise ConfigEntryAuthFailed from e
            raise

        return self._flatten(vehicle)

    def _flatten(
        self, data: dict[str, Any], parent: str | None = None
    ) -> dict[str, Any]:
        """Flatten the data structure."""
        result = {}
        for key, value in data.items():
            if parent:
                key = f"{parent}_{key}"
            if isinstance(value, dict):
                result.update(self._flatten(value, key))
            else:
                result[key] = value
        return result
