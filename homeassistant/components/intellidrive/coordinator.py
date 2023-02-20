"""Coordinator for Reisinger Intellidrive."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .device import ReisingerSlidingDoorDeviceApi

_LOGGER = logging.getLogger(__name__)


class ReisingerCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Openreisinger data."""

    config_entry: ConfigEntry
    device: ReisingerSlidingDoorDeviceApi

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: ReisingerSlidingDoorDeviceApi,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self.device = device
        self.config_entry = config_entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch devicedatas from intellidrive device."""

        data = await self.device.async_get_door_state()
        if data is None:
            raise UpdateFailed("Unable to connect to Intellidrive device")
        return data
