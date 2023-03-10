"""Roborock Coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.api import RoborockMqttClient
from roborock.exceptions import RoborockException, RoborockTimeout
from roborock.typing import RoborockDeviceProp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    ACCEPTABLE_NUMBER_OF_TIMEOUTS = 3

    def __init__(self, hass: HomeAssistant, client: RoborockMqttClient) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms: list[str] = []
        self._devices_prop: dict[str, RoborockDeviceProp] = {}
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def _get_device_prop(self, device_id: str) -> None:
        """Get device properties."""
        device_prop = await self.api.get_prop(device_id)
        if device_prop:
            if device_id in self._devices_prop:
                self._devices_prop[device_id].update(device_prop)
            else:
                self._devices_prop[device_id] = device_prop

    async def _async_update_data(self) -> dict[str, RoborockDeviceProp]:
        """Update data via library."""
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        try:
            for device_id, _ in self.api.device_map.items():
                await self._get_device_prop(device_id)
        except RoborockTimeout as ex:
            if self._devices_prop and self._timeout_countdown > 0:
                _LOGGER.debug(
                    "Timeout updating coordinator. Acceptable timeouts countdown = %s",
                    self._timeout_countdown,
                )
                self._timeout_countdown -= 1
            else:
                raise UpdateFailed(ex) from ex
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        if self._devices_prop:
            return self._devices_prop
        raise UpdateFailed("No device props found")
