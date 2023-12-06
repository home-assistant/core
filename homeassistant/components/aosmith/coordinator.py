"""The data update coordinator for the A. O. Smith integration."""

from asyncio import timeout
import logging
from typing import Any

from py_aosmith import (
    AOSmithAPIClient,
    AOSmithInvalidCredentialsException,
    AOSmithUnknownException,
)

from homeassistant.core import HomeAssistant
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
            async with timeout(10):
                devices = await self.client.get_devices()

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
        except (AOSmithInvalidCredentialsException, AOSmithUnknownException) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
