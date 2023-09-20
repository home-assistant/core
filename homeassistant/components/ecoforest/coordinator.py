"""The ecoforest coordinator."""


import logging

import async_timeout
from pyecoforest.api import EcoforestApi
from pyecoforest.exceptions import EcoforestAuthenticationRequired, EcoforestError
from pyecoforest.models.device import Device

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EcoforestCoordinator(DataUpdateCoordinator[Device]):
    """DataUpdateCoordinator to gather data from ecoforest device."""

    def __init__(self, hass: HomeAssistant, api: EcoforestApi, host: str) -> None:
        """Initialize DataUpdateCoordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name="ecoforest",
            update_interval=POLLING_INTERVAL,
        )
        self.api = api
        self.host = host

    async def _async_update_data(self) -> Device:
        """Fetch all device and sensor data from api."""
        try:
            async with async_timeout.timeout(10):
                data: Device = await self.api.get()
                _LOGGER.debug("Ecoforest data: %s", data)
                return data
        except EcoforestAuthenticationRequired as err:
            raise ConfigEntryAuthFailed from err
        except EcoforestError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
