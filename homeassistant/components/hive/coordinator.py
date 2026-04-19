"""Data update coordinator for the Hive integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

from apyhiveapi import Hive

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type HiveDeviceData = dict[str, dict[str, Any]]

# Maps hive.session.deviceList keys to the coroutine that returns formatted data.
_PLATFORM_GETTERS: dict[
    str, Callable[[Hive, dict[str, Any]], Awaitable[dict[str, Any]]]
] = {
    "binary_sensor": lambda hive, dev: hive.sensor.getSensor(dev),
    "climate": lambda hive, dev: hive.heating.getClimate(dev),
    "light": lambda hive, dev: hive.light.getLight(dev),
    "sensor": lambda hive, dev: hive.sensor.getSensor(dev),
    "switch": lambda hive, dev: hive.switch.getSwitch(dev),
    "water_heater": lambda hive, dev: hive.hotwater.getWaterHeater(dev),
}


class HiveDataUpdateCoordinator(DataUpdateCoordinator[HiveDeviceData]):
    """Manage fetching Hive device data from the apyhiveapi library."""

    def __init__(self, hass: HomeAssistant, hive: Hive) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self.hive = hive

    async def _async_update_data(self) -> HiveDeviceData:
        """Fetch the latest state for every known Hive device."""
        data: HiveDeviceData = {}
        for platform, getter in _PLATFORM_GETTERS.items():
            for device in self.hive.session.deviceList.get(platform) or []:
                await self.hive.session.updateData(device)
                updated = await getter(self.hive, device)
                data[updated["hiveID"]] = updated
        return data
