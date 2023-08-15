"""DataUpdateCoordinator for the Fast.com integration."""
from __future__ import annotations

from datetime import timedelta

from fastdotcom import fast_com

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class FastdotcomDataUpdateCoordindator(DataUpdateCoordinator):
    """Class to manage fetching Fast.com data API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordintor for Fast.com."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from Fast.com."""
        try:
            return await self.hass.async_add_executor_job(fast_com)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Fast.com: {err}") from err
