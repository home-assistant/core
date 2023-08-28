"""Update coordinators for Yardian."""

from __future__ import annotations

import asyncio
import datetime
import logging

from pyyardian import (
    AsyncYardianClient,
    NetworkException,
    NotAuthorizedException,
    YardianDeviceState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)


class YardianUpdateCoordinator(DataUpdateCoordinator[YardianDeviceState]):
    """Coordinator for Yardian API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        controller: AsyncYardianClient,
    ) -> None:
        """Initialize Yardian API communication."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_method=self._async_update_data,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

        self.controller = controller
        self.yid = entry.data["yid"]
        self._name = entry.title
        self._model = entry.data["model"]

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
                return await self.controller.fetch_device_state()

        except asyncio.TimeoutError as e:
            raise UpdateFailed("Communication with Device was time out") from e
        except NotAuthorizedException as e:
            raise UpdateFailed("Invalid access token") from e
        except NetworkException as e:
            raise UpdateFailed("Failed to communicate with Device") from e
