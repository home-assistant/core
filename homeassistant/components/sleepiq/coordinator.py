"""Coordinator for SleepIQ."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from asyncsleepiq import AsyncSleepIQ, SleepIQAPIException, SleepIQTimeoutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
LONGER_UPDATE_INTERVAL = timedelta(minutes=5)
SLEEP_DATA_UPDATE_INTERVAL = timedelta(hours=1)  # Sleep data doesn't change frequently


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


class SleepIQSleepDataCoordinator(DataUpdateCoordinator[None]):
    """SleepIQ sleep health data coordinator."""

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
            name=f"{config_entry.data[CONF_USERNAME]}@SleepIQSleepData",
            update_interval=SLEEP_DATA_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch sleep health data from API via asyncsleepiq library."""
        try:
            await asyncio.gather(
                *[
                    sleeper.fetch_sleep_data()
                    for bed in self.client.beds.values()
                    for sleeper in bed.sleepers
                ]
            )
        except SleepIQTimeoutException as err:
            raise UpdateFailed(f"Timed out fetching SleepIQ sleep data: {err}") from err
        except SleepIQAPIException as err:
            raise UpdateFailed(f"Failed to fetch SleepIQ sleep data: {err}") from err


@dataclass
class SleepIQData:
    """Data for the sleepiq integration."""

    data_coordinator: SleepIQDataUpdateCoordinator
    pause_coordinator: SleepIQPauseUpdateCoordinator
    sleep_data_coordinator: SleepIQSleepDataCoordinator
    client: AsyncSleepIQ
