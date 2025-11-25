"""Coordinator for Prana integration.

Responsible for polling the device REST endpoints and normalizing data for entities.
"""

from datetime import timedelta
import logging
from typing import Any

from prana_local_api_client.exceptions import (
    PranaApiCommunicationError,
    PranaApiUpdateFailed,
)
from prana_local_api_client.prana_api_client import PranaLocalApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PranaFanType, PranaSensorType

_LOGGER = logging.getLogger(__name__)


class PranaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Universal coordinator for Prana (fan, switch, sensor, light data)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, prana_config: str | None
    ) -> None:
        """Initialize the Prana data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=10),
            update_method=self._async_update_data,
            config_entry=entry,
        )
        self.entry = entry
        self.max_speed: int | None = None

        host = self.entry.data.get("host")
        if not host:
            raise ValueError("Host is not specified in the config entry data")
        self.api_client = PranaLocalApiClient(host=host, port=80)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and normalize device state for all platforms."""
        _LOGGER.debug("Fetching data from Prana device")

        try:
            async with self.api_client:
                state = await self.api_client.get_state()
        except PranaApiUpdateFailed as err:
            raise UpdateFailed(f"HTTP error communicating with device: {err}") from err
        except PranaApiCommunicationError as err:
            raise UpdateFailed(
                f"Network error communicating with device: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating device: {err}") from err

        self.max_speed = state[PranaFanType.EXTRACT]["max_speed"] // 10
        for key in (
            PranaFanType.BOUNDED,
            PranaFanType.SUPPLY,
            PranaFanType.EXTRACT,
        ):
            if key in state:
                state[key]["max_speed"] = self.max_speed

        # Convert temperatures (device provides tenths of °C)
        for temp_key in (
            PranaSensorType.INSIDE_TEMPERATURE,
            PranaSensorType.OUTSIDE_TEMPERATURE,
            PranaSensorType.INSIDE_TEMPERATURE_2,
            PranaSensorType.OUTSIDE_TEMPERATURE_2,
        ):
            if temp_key in state and isinstance(state[temp_key], (int, float)):
                state[temp_key] = state[temp_key] / 10

        _LOGGER.debug("Fetched state: %s", state)
        return state
