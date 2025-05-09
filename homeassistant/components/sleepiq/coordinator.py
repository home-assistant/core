"""Coordinator for SleepIQ."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from asyncsleepiq import AsyncSleepIQ

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
LONGER_UPDATE_INTERVAL = timedelta(minutes=5)


class SleepIQDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """SleepIQ data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: AsyncSleepIQ,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.data[CONF_USERNAME]}@SleepIQ",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        tasks = [self.client.fetch_bed_statuses()] + [
            bed.foundation.update_foundation_status()
            for bed in self.client.beds.values()
        ]
        await asyncio.gather(*tasks)


class SleepIQPauseUpdateCoordinator(DataUpdateCoordinator[None]):
    """SleepIQ data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: AsyncSleepIQ,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.data[CONF_USERNAME]}@SleepIQPause",
            update_interval=LONGER_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        await asyncio.gather(
            *[bed.fetch_pause_mode() for bed in self.client.beds.values()]
        )


@dataclass
class SleepIQData:
    """Data for the sleepiq integration."""

    data_coordinator: SleepIQDataUpdateCoordinator
    pause_coordinator: SleepIQPauseUpdateCoordinator
    client: AsyncSleepIQ
