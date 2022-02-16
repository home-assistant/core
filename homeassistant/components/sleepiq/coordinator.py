"""Coordinator for SleepIQ."""
from datetime import timedelta
import logging

from sleepyq import Sleepyq

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import BED

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


class SleepIQDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """SleepIQ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: Sleepyq,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{username}@SleepIQ", update_interval=UPDATE_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict]:
        return await self.hass.async_add_executor_job(self.update_data)

    def update_data(self) -> dict[str, dict]:
        """Get latest data from the client."""
        return {
            bed.bed_id: {BED: bed} for bed in self.client.beds_with_sleeper_status()
        }
