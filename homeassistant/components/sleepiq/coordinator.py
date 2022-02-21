"""Coordinator for SleepIQ."""
from datetime import timedelta
import logging

from asyncsleepiq import AsyncSleepIQ

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
LONGER_UPDATE_INTERVAL = timedelta(minutes=5)


class SleepIQDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """SleepIQ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncSleepIQ,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{username}@SleepIQ",
            update_method=client.fetch_bed_statuses,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client


class SleepIQPauseUpdateCoordinator(DataUpdateCoordinator[None]):
    """SleepIQ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncSleepIQ,
        username: str,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=f"{username}@SleepIQPause",
            update_interval=LONGER_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        for bed in self.client.beds.values():
            await bed.fetch_pause_mode()
