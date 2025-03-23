"""DataUpdateCoordinator for the Fast.com integration."""

from __future__ import annotations

from datetime import timedelta
from functools import partial

from fastdotcom2 import fast_com2

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_INTERVAL, DOMAIN, LOGGER

type FastdotcomConfigEntry = ConfigEntry["FastdotcomDataUpdateCoordinator"]


class FastdotcomDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Class to manage fetching Fast.com data API."""

    def __init__(self, hass: HomeAssistant, entry: FastdotcomConfigEntry) -> None:
        """Initialize the coordinator for Fast.com."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, float]:
        """Run an executor job to retrieve Fast.com data."""
        try:
            return await self.hass.async_add_executor_job(
                partial(fast_com2, max_time=10)
            )
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with Fast.com: {exc}") from exc

    async def async_refresh(self) -> None:
        """Override async_refresh to let UpdateFailed propagate."""
        self.data = await self._async_update_data()
