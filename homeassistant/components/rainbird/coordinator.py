"""Update coordinators for rainbird."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import datetime
import logging
from typing import TypeVar

import async_timeout
from pyrainbird.async_client import AsyncRainbirdController, RainbirdApiException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, TIMEOUT_SECONDS

UPDATE_INTERVAL = datetime.timedelta(minutes=1)
MANUFACTURER = "Rain Bird"

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass
class ConfigData:
    """Global data used by a config entry."""

    serial_number: str
    controller: AsyncRainbirdController

    @property
    def device_info(self) -> DeviceInfo:
        """Information about the device for this config."""
        return DeviceInfo(
            default_name=MANUFACTURER,
            identifiers={(DOMAIN, self.serial_number)},
            manufacturer=MANUFACTURER,
        )


class RainbirdUpdateCoordinator(DataUpdateCoordinator[_T]):
    """Coordinator for rainbird API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_method: Callable[[], Awaitable[_T]],
    ) -> None:
        """Initialize ZoneStateUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_method=update_method,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> _T:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(TIMEOUT_SECONDS):
                return await self.update_method()  # type: ignore[misc]
        except RainbirdApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
