"""Update coordinators for Yardian."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging

import async_timeout
from pyyardian import AsyncYardianClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_WATERING_DURATION, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)


@dataclass
class YardianDeviceState:
    """Data retrieved from a Yardian device."""

    zones: list[list]
    active_zones: set[int]


class YardianUpdateCoordinator(DataUpdateCoordinator[YardianDeviceState]):
    """Coordinator for Yardian API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        controller: AsyncYardianClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_method=self._async_update_data,
            update_interval=SCAN_INTERVAL,
        )

        self._controller = controller
        self._name = entry.title
        self._model = entry.data["model"]
        self._yid = entry.data["yid"]
        self._amount_of_zones = entry.data["zones"]

    @property
    def controller(self) -> AsyncYardianClient:
        """Return the API client for the device."""
        return self._controller

    @property
    def yid(self) -> str:
        """Return the device id."""
        return self._yid

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self._yid)},
            manufacturer=MANUFACTURER,
        )

    def getZoneDefaultWateringDuration(self, zone_id) -> int:
        """Return default watering duration for a given zone."""
        return DEFAULT_WATERING_DURATION

    async def _async_update_data(self) -> YardianDeviceState:
        """Fetch data from Yardian device."""
        try:
            async with async_timeout.timeout(10):
                zones = await self._controller.fetch_zone_info(self._amount_of_zones)
                active_zones = await self._controller.fetch_active_zones()
                return YardianDeviceState(zones=zones, active_zones=active_zones)

        except Exception as err:
            raise UpdateFailed(f"Failed to communicate with Device: {err}") from err
