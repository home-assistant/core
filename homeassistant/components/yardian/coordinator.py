"""Update coordinators for Yardian."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
import logging

from pyyardian import AsyncYardianClient, NetworkException, NotAuthorizedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER

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

        self.controller = controller
        self.yid = entry.data["yid"]
        self._name = entry.title
        self._model = entry.data["model"]
        self._amount_of_zones = entry.data["zones"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self.yid)},
            manufacturer=MANUFACTURER,
            model=self._model,
        )

    async def _async_update_data(self) -> YardianDeviceState:
        """Fetch data from Yardian device."""
        try:
            async with asyncio.timeout(10):
                zones = await self.controller.fetch_zone_info(self._amount_of_zones)
                active_zones = await self.controller.fetch_active_zones()
                return YardianDeviceState(zones=zones, active_zones=active_zones)

        except asyncio.TimeoutError as e:
            raise UpdateFailed("Communication with Device was time out") from e
        except NotAuthorizedException as e:
            raise UpdateFailed("Invalid access token") from e
        except NetworkException as e:
            raise UpdateFailed("Failed to communicate with Device") from e
