"""DataUpdateCoordinator for the Fast.com integration."""
from __future__ import annotations

from datetime import timedelta

from fastdotcom import fast_com

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_INTERVAL, DOMAIN, LOGGER


class FastdotcomDataUpdateCoordindator(DataUpdateCoordinator):
    """Class to manage fetching Fast.com data API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordintor for Fast.com."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Run an executor job to retrieve Fast.com data."""
        try:
            return await self.hass.async_add_executor_job(fast_com)
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with Fast.com: {exc}") from exc
