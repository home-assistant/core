"""Coordinator for fetching data from fitbit API."""

import asyncio
from dataclasses import dataclass
import datetime
import logging
from typing import Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FitbitApi
from .exceptions import FitbitApiException, FitbitAuthException
from .model import FitbitDevice

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = datetime.timedelta(minutes=30)
TIMEOUT = 10


class FitbitDeviceCoordinator(DataUpdateCoordinator[dict[str, FitbitDevice]]):
    """Coordinator for fetching fitbit devices from the API."""

    def __init__(self, hass: HomeAssistant, api: FitbitApi) -> None:
        """Initialize FitbitDeviceCoordinator."""
        super().__init__(hass, _LOGGER, name="Fitbit", update_interval=UPDATE_INTERVAL)
        self._api = api

    async def _async_update_data(self) -> dict[str, FitbitDevice]:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(TIMEOUT):
            try:
                devices = await self._api.async_get_devices()
            except FitbitAuthException as err:
                raise ConfigEntryAuthFailed(err) from err
            except FitbitApiException as err:
                raise UpdateFailed(err) from err
        return {device.id: device for device in devices}


@dataclass
class FitbitData:
    """Config Entry global data."""

    api: FitbitApi
    device_coordinator: FitbitDeviceCoordinator | None
