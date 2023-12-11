"""The data update coordinator for the A. O. Smith integration."""

import logging
from typing import Any

from py_aosmith import (
    AOSmithAPIClient,
    AOSmithInvalidCredentialsException,
    AOSmithUnknownException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FAST_INTERVAL, REGULAR_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AOSmithCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Custom data update coordinator for A. O. Smith integration."""

    def __init__(self, hass: HomeAssistant, client: AOSmithAPIClient) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=REGULAR_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch latest data from API."""
        try:
            devices = await self.client.get_devices()
        except AOSmithInvalidCredentialsException as err:
            raise ConfigEntryAuthFailed from err
        except AOSmithUnknownException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        mode_pending = any(
            device.get("data", {}).get("modePending") for device in devices
        )
        setpoint_pending = any(
            device.get("data", {}).get("temperatureSetpointPending")
            for device in devices
        )

        if mode_pending or setpoint_pending:
            self.update_interval = FAST_INTERVAL
        else:
            self.update_interval = REGULAR_INTERVAL

        return {device.get("junctionId"): device for device in devices}
