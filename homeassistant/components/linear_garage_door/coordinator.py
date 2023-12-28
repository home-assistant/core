"""DataUpdateCoordinator for Linear."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from linear_garage_door import Linear
from linear_garage_door.errors import InvalidLoginError, ResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class LinearUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for Linear."""

    _email: str
    _password: str
    _device_id: str
    _site_id: str
    _devices: list[dict[str, list[str] | str]] | None
    _linear: Linear

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize DataUpdateCoordinator for Linear."""
        self._email = entry.data["email"]
        self._password = entry.data["password"]
        self._device_id = entry.data["device_id"]
        self._site_id = entry.data["site_id"]
        self._devices = None

        super().__init__(
            hass,
            _LOGGER,
            name="Linear Garage Door",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the data for Linear."""

        linear = Linear()

        try:
            await linear.login(
                email=self._email,
                password=self._password,
                device_id=self._device_id,
            )
        except InvalidLoginError as err:
            if (
                str(err)
                == "Login error: Login provided is invalid, please check the email and password"
            ):
                raise ConfigEntryAuthFailed from err
            raise ConfigEntryNotReady from err
        except ResponseError as err:
            raise ConfigEntryNotReady from err

        if not self._devices:
            self._devices = await linear.get_devices(self._site_id)

        data = {}

        for device in self._devices:
            device_id = str(device["id"])
            state = await linear.get_device_state(device_id)
            data[device_id] = {"name": device["name"], "subdevices": state}

        await linear.close()

        return data
