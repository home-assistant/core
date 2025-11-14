"""Coordinator for Prana integration.

Responsible for polling the device REST endpoints and normalizing data for entities.
"""

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and normalize device state for all platforms."""
        _LOGGER.debug("Fetching data from Prana device")
        try:
            state = await self.async_get_state()
        except UpdateFailed:
            # Pass through UpdateFailed unchanged
            raise
        except (ClientError, TimeoutError) as err:  # network related
            raise UpdateFailed(
                f"Network error communicating with device: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating device: {err}") from err

        # Normalize fan max speeds (device reports *10 values)
        try:
            self.max_speed = state[PranaFanType.EXTRACT]["max_speed"] // 10
            for key in (
                PranaFanType.BOUNDED,
                PranaFanType.SUPPLY,
                PranaFanType.EXTRACT,
            ):
                if key in state:
                    state[key]["max_speed"] = self.max_speed
        except Exception:  # noqa: BLE001 - ignore malformed fan data
            _LOGGER.debug("Fan speed normalization skipped due to malformed data")

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

    async def async_get_state(self) -> dict[str, Any]:
        """Perform the HTTP GET to retrieve raw state from device."""
        async with (
            ClientSession() as session,
            session.get(f"http://{self.entry.data.get('host')}:80/getState") as resp,
        ):
            if resp.status != 200:
                raise UpdateFailed(f"HTTP error {resp.status}")
            return await resp.json()
