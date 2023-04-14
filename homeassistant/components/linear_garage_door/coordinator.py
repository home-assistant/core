"""DataUpdateCoordinator for Linear."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from linear_garage_door import Linear

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class LinearUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for Linear."""

    _email: str
    _password: str
    _device_id: str
    _site_id: str
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

        super().__init__(
            hass,
            _LOGGER,
            name="Linear Garage Door",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the data for Linear."""

        linear = Linear()

        await linear.login(
            email=self._email,
            password=self._password,
            device_id=self._device_id,
        )

        devices = await linear.get_devices(self._site_id)
        data = {}

        for device in devices:
            device_id = str(device["id"])
            state = await linear.get_device_state(device_id)
            data[device_id] = {"name": device["name"], "subdevices": state}

        await linear.close()

        return data
