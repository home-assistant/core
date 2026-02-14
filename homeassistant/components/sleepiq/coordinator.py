"""Coordinator for SleepIQ."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from asyncsleepiq import AsyncSleepIQ

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        """Fetch sleep health data from API."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

        tasks = []
        for bed in self.client.beds.values():
            for sleeper in bed.sleepers:
                tasks.append(self._fetch_sleeper_data(sleeper, yesterday))

        await asyncio.gather(*tasks)

    async def _fetch_sleeper_data(self, sleeper, date_str: str) -> None:
        params = {
            "date": date_str,
            "interval": "D1",
            "sleeper": sleeper.sleeper_id,
            "includeSlices": "false"
        }
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        endpoint = f"sleepData?{param_str}"

        try:
            data = await self.client.get(endpoint)
        except Exception as err:
            _LOGGER.debug(
                "Error fetching sleep data for %s: %s",
                sleeper.name,
                err,
            )
            return

        if data:
            # Update sleeper attributes with sleep health metrics
            # NOTE: totalSleepSessionTime is always 0, use inBed instead for duration
            sleeper.sleep_duration = data["inBed"]  # seconds
            sleeper.sleep_score = data["avgSleepIQ"]
            sleeper.heart_rate = data["avgHeartRate"]
            sleeper.respiratory_rate = data["avgRespirationRate"]

            _LOGGER.debug(
                "Updated sleep data for %s: score=%s, duration=%sh, hr=%s, rr=%s",
                sleeper.name,
                sleeper.sleep_score,
                round(sleeper.sleep_duration / 3600, 1) if sleeper.sleep_duration else None,
                sleeper.heart_rate,
                sleeper.respiratory_rate,
            )


@dataclass
class SleepIQData:
    """Data for the sleepiq integration."""

    data_coordinator: SleepIQDataUpdateCoordinator
    pause_coordinator: SleepIQPauseUpdateCoordinator
    sleep_data_coordinator: SleepIQSleepDataCoordinator
    client: AsyncSleepIQ
