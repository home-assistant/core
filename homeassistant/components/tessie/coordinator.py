"""Tessie Data Coordinator."""

from datetime import timedelta
from http import HTTPStatus
import logging
from time import time
from typing import Any

from aiohttp import ClientResponseError
from tesla_fleet_api import EnergySpecific
from tesla_fleet_api.exceptions import InvalidToken, MissingToken, TeslaFleetError
from tessie_api import get_state

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import TessieState

# This matches the update interval Tessie performs server side
TESSIE_SYNC_INTERVAL = 10
TESSIE_FLEET_API_SYNC_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


def flatten(data: dict[str, Any], parent: str | None = None) -> dict[str, Any]:
    """Flatten the data structure."""
    result = {}
    for key, value in data.items():
        if parent:
            key = f"{parent}_{key}"
        if isinstance(value, dict):
            result.update(flatten(value, key))
        else:
            result[key] = value
    return result


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

        # Tessie always returns cached data with a status of "online"
        # We need to check the timestamp to determine if the vehicle is actually asleep
        if data["vehicle_state"]["timestamp"] < (time() - 60) * 1000:
            data["state"] = TessieState.ASLEEP

        self.data = flatten(data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Tessie API."""
        try:
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

        # Tessie always returns cached data with a status of "online"
        # We need to check the timestamp to determine if the vehicle is actually asleep
        if vehicle["vehicle_state"]["timestamp"] < (time() - 60) * 1000:
            vehicle["state"] = TessieState.ASLEEP

        return flatten(vehicle)


class TessieEnergySiteLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site live status from the Tessie API."""

    def __init__(self, hass: HomeAssistant, api: EnergySpecific) -> None:
        """Initialize Tessie Energy Site Live coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tessie Energy Site Live",
            update_interval=TESSIE_FLEET_API_SYNC_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Tessie API."""

        try:
            data = (await self.api.live_status())["response"]
        except (InvalidToken, MissingToken) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Convert Wall Connectors from array to dict
        data["wall_connectors"] = {
            wc["din"]: wc for wc in (data.get("wall_connectors") or [])
        }

        return data


class TessieEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site info from the Tessie API."""

    def __init__(self, hass: HomeAssistant, api: EnergySpecific) -> None:
        """Initialize Tessie Energy Info coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tessie Energy Site Info",
            update_interval=TESSIE_FLEET_API_SYNC_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Tessie API."""

        try:
            data = (await self.api.site_info())["response"]
        except (InvalidToken, MissingToken) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        return flatten(data)
