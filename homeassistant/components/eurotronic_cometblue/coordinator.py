"""Provides the DataUpdateCoordinator for Comet Blue."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue, InvalidByteValueError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MAX_RETRIES

SCAN_INTERVAL = timedelta(minutes=5)
LOGGER = logging.getLogger(__name__)
COMMAND_RETRY_INTERVAL = 2.5

type CometBlueConfigEntry = ConfigEntry[CometBlueDataUpdateCoordinator]


@dataclass
class CometBlueCoordinatorData:
    """Data stored by the coordinator."""

    temperatures: dict[str, float | int] = field(default_factory=dict)
    holiday: dict = field(default_factory=dict)
    battery: int | None = None


class CometBlueDataUpdateCoordinator(DataUpdateCoordinator[CometBlueCoordinatorData]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CometBlueConfigEntry,
        cometblue: AsyncCometBlue,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            config_entry=entry,
            logger=LOGGER,
            name=f"Comet Blue {cometblue.client.address}",
            update_interval=SCAN_INTERVAL,
        )
        self.device = cometblue
        self.address = cometblue.client.address
        self.data = CometBlueCoordinatorData()

    async def send_command(
        self,
        function: Callable[..., Awaitable[dict[str, Any] | None]],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Send command to device."""

        LOGGER.debug("Updating device %s with '%s'", self.name, payload)
        retry_count = 0
        while retry_count < MAX_RETRIES:
            retry_count += 1
            try:
                async with self.device:
                    return await function(**payload)
            except (InvalidByteValueError, TimeoutError, BleakError) as ex:
                if retry_count >= MAX_RETRIES:
                    raise HomeAssistantError(
                        f"Error sending command to '{self.name}': {ex}"
                    ) from ex
                LOGGER.info(
                    "Retry sending command to %s after %s (%s)",
                    self.name,
                    type(ex).__name__,
                    ex,
                )
                await asyncio.sleep(COMMAND_RETRY_INTERVAL)
            except ValueError as ex:
                raise ServiceValidationError(
                    f"Invalid payload '{payload}' for '{self.name}': {ex}"
                ) from ex
        return None

    async def _async_update_data(self) -> CometBlueCoordinatorData:
        """Poll the device."""
        data = CometBlueCoordinatorData()

        retry_count = 0

        while retry_count < MAX_RETRIES and not data.temperatures:
            try:
                retry_count += 1
                async with self.device:
                    # temperatures are required and must trigger a retry if not available
                    if not data.temperatures:
                        data.temperatures = await self.device.get_temperature_async()
                    # holiday and battery are optional and should not trigger a retry
                    try:
                        if not data.holiday:
                            data.holiday = await self.device.get_holiday_async(1) or {}
                        if not data.battery:
                            data.battery = await self.device.get_battery_async()
                    except InvalidByteValueError as ex:
                        LOGGER.warning(
                            "Failed to retrieve optional data for %s: %s (%s)",
                            self.name,
                            type(ex).__name__,
                            ex,
                        )
            except (InvalidByteValueError, TimeoutError, BleakError) as ex:
                if retry_count >= MAX_RETRIES:
                    raise UpdateFailed(
                        f"Error retrieving data: {ex}", retry_after=30
                    ) from ex
                LOGGER.info(
                    "Retry updating %s after error: %s (%s)",
                    self.name,
                    type(ex).__name__,
                    ex,
                )
                await asyncio.sleep(COMMAND_RETRY_INTERVAL)
            except Exception as ex:
                raise UpdateFailed(
                    f"({type(ex).__name__}) {ex}", retry_after=30
                ) from ex

        # If one value was not retrieved correctly, keep the old value
        if not data.holiday:
            data.holiday = self.data.holiday
        if not data.battery:
            data.battery = self.data.battery
        LOGGER.debug("Received data for %s: %s", self.name, data)
        return data
