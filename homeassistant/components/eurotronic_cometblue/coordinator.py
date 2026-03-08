"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from bleak.exc import BleakError
from eurotronic_cometblue_ha import AsyncCometBlue, InvalidByteValueError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALL_TEMPERATURES, DEFAULT_RETRY_COUNT

SCAN_INTERVAL = timedelta(minutes=5)
LOGGER = logging.getLogger(__name__)

type CometBlueConfigEntry = ConfigEntry[CometBlueDataUpdateCoordinator]


class DeviceUnavailable(HomeAssistantError):
    """Raised if device can't be found."""


class CometBlueDataUpdateCoordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    failed_update_count: int = 0

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cometblue: AsyncCometBlue,
        device_info: DeviceInfo,
        retry_count: int = DEFAULT_RETRY_COUNT,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            config_entry=entry,
            logger=LOGGER,
            name=f"Comet Blue {cometblue.client.address}",
            update_interval=SCAN_INTERVAL,
        )
        self.device: AsyncCometBlue = cometblue
        self.address = cometblue.client.address
        self.data: dict[str, Any] = {}
        self.device_info = device_info
        self.retry_count = retry_count

    async def send_command(
        self, function: str, payload: dict[str, Any], caller_entity_id: str
    ) -> dict[str, Any] | None:
        """Send command to device."""

        LOGGER.debug("Updating device with '%s' from '%s'", caller_entity_id, payload)
        retry_count = 0
        while retry_count < self.retry_count:
            try:
                async with self.device:
                    if not self.device.connected:
                        raise ConfigEntryNotReady(
                            f"Failed to connect to '{self.device.device.address}'"
                        )
                    return await getattr(self.device, function)(**payload)
            except (InvalidByteValueError, TimeoutError, BleakError) as ex:
                retry_count += 1
                if retry_count >= self.retry_count:
                    raise HomeAssistantError(
                        f"Error sending command '{payload}' to '{caller_entity_id}': {ex}"
                    ) from ex
                LOGGER.info(
                    "Retrying command '%s' to '%s' after %s (%s)",
                    payload,
                    caller_entity_id,
                    type(ex).__name__,
                    ex,
                )
                await asyncio.sleep(2.5)
            except ValueError as ex:
                raise ServiceValidationError(
                    f"Invalid payload '{payload}' for '{caller_entity_id}': {ex}"
                ) from ex
        return None

    async def _async_update_data(self) -> dict[str, bytes]:
        """Poll the device."""
        data: dict = {}

        retry_count = 0
        retrieved_temperatures: dict = {}
        battery: int | None = None
        holiday: dict | None = None

        while (
            retry_count < self.retry_count
            and not retrieved_temperatures
            and battery is None
            and holiday is None
        ):
            async with self.device:
                if not self.device.connected:
                    raise ConfigEntryNotReady(
                        f"Failed to connect to '{self.device.device.address}'"
                    )
                try:
                    # temperatures are required and must trigger a retry if not available
                    if not retrieved_temperatures:
                        retrieved_temperatures = (
                            await self.device.get_temperature_async()
                        )
                    # battery and holiday are optional and should not trigger a retry
                    try:
                        if battery is None:
                            battery = await self.device.get_battery_async()
                        if not holiday:
                            holiday = await self.device.get_holiday_async(1) or {}
                    except InvalidByteValueError as ex:
                        LOGGER.warning(
                            "Failed to retrieve optional data: %s (%s)",
                            type(ex).__name__,
                            ex,
                        )
                except (InvalidByteValueError, TimeoutError, BleakError) as ex:
                    retry_count += 1
                    if retry_count >= self.retry_count:
                        self.failed_update_count += 1
                        raise UpdateFailed(
                            f"Error retrieving data: {ex}", retry_after=30
                        ) from ex
                    LOGGER.info(
                        "Retrying after %s (%s)",
                        type(ex).__name__,
                        ex,
                    )
                    await asyncio.sleep(2.5)
                except Exception as ex:
                    raise UpdateFailed(
                        f"({type(ex).__name__}) {ex}", retry_after=30
                    ) from ex

        # If one value was not retrieved correctly, keep the old value
        data = {
            "battery": battery if battery is not None else self.data.get("battery"),
            "holiday": holiday if holiday is not None else self.data.get("holiday", {}),
            **{
                k: retrieved_temperatures.get(k) or self.data.get(k)
                for k in CONF_ALL_TEMPERATURES
            },
        }
        LOGGER.debug("Received data: %s", data)
        return data
