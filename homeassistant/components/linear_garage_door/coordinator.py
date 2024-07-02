"""DataUpdateCoordinator for Linear."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from linear_garage_door import Linear
from linear_garage_door.errors import InvalidLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class LinearDevice:
    """Linear device dataclass."""

    name: str
    subdevices: dict[str, dict[str, str]]


class LinearUpdateCoordinator(DataUpdateCoordinator[dict[str, LinearDevice]]):
    """DataUpdateCoordinator for Linear."""

    _devices: list[dict[str, Any]] | None = None
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize DataUpdateCoordinator for Linear."""
        super().__init__(
            hass,
            _LOGGER,
            name="Linear Garage Door",
            update_interval=timedelta(seconds=60),
        )
        self.site_id = self.config_entry.data["site_id"]

    async def _async_update_data(self) -> dict[str, LinearDevice]:
        """Get the data for Linear."""

        async def update_data(linear: Linear) -> dict[str, Any]:
            if not self._devices:
                self._devices = await linear.get_devices(self.site_id)

            data = {}

            for device in self._devices:
                device_id = str(device["id"])
                state = await linear.get_device_state(device_id)
                data[device_id] = LinearDevice(device["name"], state)
            return data

        return await self.execute(update_data)

    async def execute[_T](self, func: Callable[[Linear], Awaitable[_T]]) -> _T:
        """Execute an API call."""
        linear = Linear()
        try:
            await linear.login(
                email=self.config_entry.data["email"],
                password=self.config_entry.data["password"],
                device_id=self.config_entry.data["device_id"],
                client_session=async_get_clientsession(self.hass),
            )
        except InvalidLoginError as err:
            if (
                str(err)
                == "Login error: Login provided is invalid, please check the email and password"
            ):
                raise ConfigEntryAuthFailed from err
            raise ConfigEntryNotReady from err
        result = await func(linear)
        await linear.close()
        return result
