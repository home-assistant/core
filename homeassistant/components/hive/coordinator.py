"""Data update coordinator for the Hive integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

from apyhiveapi import Hive

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type HiveDeviceData = dict[tuple[str, str], dict[str, Any]]

# Maps hive.session.deviceList keys to the coroutine that returns formatted data.
_PLATFORM_GETTERS: dict[
    str, Callable[[Hive, dict[str, Any]], Awaitable[dict[str, Any]]]
] = {
    # Both binary_sensor and sensor device types use the same library getter.
    "binary_sensor": lambda hive, dev: hive.sensor.getSensor(dev),
    "climate": lambda hive, dev: hive.heating.getClimate(dev),
    "light": lambda hive, dev: hive.light.getLight(dev),
    "sensor": lambda hive, dev: hive.sensor.getSensor(dev),
    "switch": lambda hive, dev: hive.switch.getSwitch(dev),
    "water_heater": lambda hive, dev: hive.hotwater.getWaterHeater(dev),
}


class HiveDataUpdateCoordinator(DataUpdateCoordinator[HiveDeviceData]):
    """Manage fetching Hive device data from the apyhiveapi library."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, hive: Hive
    ) -> None:
        """Initialize the coordinator."""
        # The coordinator reads from the library's local cache every 15 seconds.
        # Actual cloud API calls are gated by the library's own scan_interval
        # (default 120 s, configurable via CONF_SCAN_INTERVAL in the options flow).
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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
                hive_id = updated.get("hiveID")
                hive_type = updated.get("hiveType")
                if hive_id is None or hive_type is None:
                    raise UpdateFailed(
                        f"Device data for platform '{platform}' is missing 'hiveID' or 'hiveType': {updated!r}"
                    )
                # Key by (hiveID, hiveType) rather than hiveID alone.
                # Some devices (e.g. Heating_Heat_On_Demand switches) share a
                # hiveID with the climate thermostat for the same zone, so a
                # plain hiveID key would let the switch entry overwrite the
                # climate entry and vice-versa.
                data[(hive_id, hive_type)] = updated
        return data
