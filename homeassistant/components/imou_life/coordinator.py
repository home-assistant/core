import asyncio
import logging
from datetime import timedelta

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyimouapi.ha_device import ImouHaDeviceManager

_LOGGER = logging.getLogger(__name__)


class ImouDataUpdateCoordinator(DataUpdateCoordinator):
    """DATA UPDATE COORDINATOR"""

    def __init__(self, hass: HomeAssistant, device_manager: ImouHaDeviceManager):
        _LOGGER.info("ImouDataUpdateCoordinator init")
        super().__init__(
            hass,
            _LOGGER,
            name="ImouDataUpdateCoordinator",
            update_interval=timedelta(seconds=60),
            always_update=True
        )
        self._device_manager = device_manager
        self._devices = []

    @property
    def devices(self):
        return self._devices

    @property
    def device_manager(self):
        return self._device_manager

    async def _async_setup(self):
        """Set up the coordinator

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        devices_list = await self._device_manager.async_get_devices()
        for device in devices_list:
            self._devices.append(device)

    async def async_update_all_device(self) -> bool:
        await asyncio.gather(*[self._device_manager.async_update_device_status(device) for device in self._devices],
                             return_exceptions=True)
        return True

    async def _async_update_data(self):
        _LOGGER.info("ImouDataUpdateCoordinator update_data")
        async with async_timeout.timeout(120):
            try:
                return await self.async_update_all_device()
            except Exception as err:
                _LOGGER.error("Error fetching data: %s" % err)
                raise UpdateFailed() from err
