"""DataUpdateCoordinator for the TickTick integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TickTickDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """A TickTick Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, ticktick_client) -> None:
        """Initialize the TickTick data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.ticktick_client = ticktick_client

    async def _async_update_data(self) -> dict:
        try:
            await self.hass.async_add_executor_job(self.ticktick_client.sync)
        except Exception as e:
            raise UpdateFailed(f"Error updating data from TickTick: {e}") from e
        else:
            return self.ticktick_client
