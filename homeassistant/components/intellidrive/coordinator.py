"""Coordinator for Reisinger Intellidrive."""

from datetime import timedelta
import logging
from typing import Any

import reisingerdrive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

# from .device import ReisingerSlidingDoorDeviceApi

_LOGGER = logging.getLogger(__name__)


class ReisingerCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from intellidrive device."""

    config_entry: ConfigEntry
    device: reisingerdrive.ReisingerSlidingDoorDeviceApi

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize ReisingerCoordinator."""
        self.device = reisingerdrive.ReisingerSlidingDoorDeviceApi(
            str(config_entry.data.get(CONF_HOST)),
            str(config_entry.data.get(CONF_TOKEN)),
            async_get_clientsession(hass),
        )
        self.config_entry = config_entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch devicedatas from intellidrive device."""

        data = await self.device.async_get_device_state()
        if data is None:
            raise UpdateFailed("Unable to connect to Intellidrive device")
        return data
