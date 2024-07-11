"""Contains the shared Coordinator for Starlink systems."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from zoneinfo import ZoneInfo

from starlink_grpc import (
    AlertDict,
    ChannelContext,
    GrpcError,
    LocationDict,
    ObstructionDict,
    StatusDict,
    get_sleep_config,
    location_data,
    reboot,
    set_sleep_config,
    set_stow_state,
    status_data,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class StarlinkData:
    """Contains data pulled from the Starlink system."""

    location: LocationDict
    sleep: tuple[int, int, bool]
    status: StatusDict
    obstruction: ObstructionDict
    alert: AlertDict


class StarlinkUpdateCoordinator(DataUpdateCoordinator[StarlinkData]):
    """Coordinates updates between all Starlink sensors defined in this file."""

    def __init__(self, hass: HomeAssistant, name: str, url: str) -> None:
        """Initialize an UpdateCoordinator for a group of sensors."""
        self.channel_context = ChannelContext(target=url)
        self.timezone = ZoneInfo(hass.config.time_zone)
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=5),
        )

    def _get_starlink_data(self) -> StarlinkData:
        """Retrieve Starlink data."""
        channel_context = self.channel_context
        status = status_data(channel_context)
        location = location_data(channel_context)
        sleep = get_sleep_config(channel_context)
        return StarlinkData(location, sleep, *status)

    async def _async_update_data(self) -> StarlinkData:
        async with asyncio.timeout(4):
            try:
                result = await self.hass.async_add_executor_job(self._get_starlink_data)
            except GrpcError as exc:
                raise UpdateFailed from exc
            return result

    async def async_stow_starlink(self, stow: bool) -> None:
        """Set whether Starlink system tied to this coordinator should be stowed."""
        async with asyncio.timeout(4):
            try:
                await self.hass.async_add_executor_job(
                    set_stow_state, not stow, self.channel_context
                )
            except GrpcError as exc:
                raise HomeAssistantError from exc

    async def async_reboot_starlink(self) -> None:
        """Reboot the Starlink system tied to this coordinator."""
        async with asyncio.timeout(4):
            try:
                await self.hass.async_add_executor_job(reboot, self.channel_context)
            except GrpcError as exc:
                raise HomeAssistantError from exc

    async def async_set_sleep_schedule_enabled(self, sleep_schedule: bool) -> None:
        """Set whether Starlink system uses the configured sleep schedule."""
        async with asyncio.timeout(4):
            try:
                await self.hass.async_add_executor_job(
                    set_sleep_config,
                    self.data.sleep[0],
                    self.data.sleep[1],
                    sleep_schedule,
                    self.channel_context,
                )
            except GrpcError as exc:
                raise HomeAssistantError from exc

    async def async_set_sleep_start(self, start: int) -> None:
        """Set Starlink system sleep schedule start time."""
        async with asyncio.timeout(4):
            try:
                await self.hass.async_add_executor_job(
                    set_sleep_config,
                    start,
                    self.data.sleep[1],
                    self.data.sleep[2],
                    self.channel_context,
                )
            except GrpcError as exc:
                raise HomeAssistantError from exc

    async def async_set_sleep_duration(self, end: int) -> None:
        """Set Starlink system sleep schedule end time."""
        duration = end - self.data.sleep[0]
        if duration < 0:
            # If the duration pushed us into the next day, add one days worth to correct that.
            duration += 1440
        async with asyncio.timeout(4):
            try:
                await self.hass.async_add_executor_job(
                    set_sleep_config,
                    self.data.sleep[0],
                    duration,
                    self.data.sleep[2],
                    self.channel_context,
                )
            except GrpcError as exc:
                raise HomeAssistantError from exc
