"""The Epion data coordinator."""

import logging
from typing import Any

from epion import Epion, EpionAuthenticationError, EpionConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REFRESH_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EpionCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Epion data update coordinator."""

    def __init__(self, hass: HomeAssistant, epion_api: Epion) -> None:
        """Initialize the Epion coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Epion",
            update_interval=REFRESH_INTERVAL,
        )
        self.epion_api = epion_api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Epion API and construct a dictionary with device IDs as keys."""
        try:
            response = await self.hass.async_add_executor_job(
                self.epion_api.get_current
            )
        except EpionAuthenticationError as err:
            _LOGGER.error("Authentication error with Epion API")
            raise ConfigEntryAuthFailed from err
        except EpionConnectionError as err:
            _LOGGER.error("Epion API connection problem")
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        device_data = {}
        for epion_device in response["devices"]:
            device_data[epion_device["deviceId"]] = epion_device
        return device_data
