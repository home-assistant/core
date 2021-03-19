"""Provides the Salus integration DataUpdateCoordinator."""
from datetime import timedelta
import logging

from async_timeout import timeout
from requests import ConnectTimeout, HTTPError
from salus.api import Api

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SalusDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Salus data."""

    def __init__(self, hass: HomeAssistantType, *, api: Api, device_id: str):
        """Initialize global Salus data updater."""
        self.salus = api
        self._device_id = device_id
        update_interval = timedelta(seconds=15)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def _update_data(self) -> dict:
        """Fetch data from Salus device."""
        return self.salus.get_device_reading(self._device_id)

    async def _async_update_data(self) -> dict:
        """Fetch data from Salus."""

        try:
            async with timeout(15):
                return await self.hass.async_add_executor_job(self._update_data)
        except (ConnectTimeout, HTTPError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error

    def _update_temperature(self, temperature: float):
        """Update the target temperature - doing a manual override."""
        self.salus.set_manual_override(self._device_id, temperature)

    async def set_manual_temperature_override(self, temperature: float):
        """Async update the target temperature - doing a manual override."""
        try:
            async with timeout(15):
                return await self.hass.async_add_executor_job(
                    lambda: self._update_temperature(temperature)
                )
        except (ConnectTimeout, HTTPError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
