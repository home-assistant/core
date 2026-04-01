"""Support for Xiaomi Miio."""

from __future__ import annotations

from datetime import timedelta
import logging

from miio.gateway.devices import SubDevice
from miio.gateway.gateway import GatewayException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .typing import XiaomiMiioConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)


class GatewayDeviceCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Xiaomi Gateway subdevices."""

    config_entry: XiaomiMiioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: XiaomiMiioConfigEntry,
        sub_device: SubDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Xiaomi Gateway subdevice {sub_device.sid}",
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.sub_device = sub_device
        # Mark as unavailable until the first update is successful
        self.last_update_success = False

    async def _async_update_data(self) -> None:
        """Fetch data from the subdevice."""
        try:
            await self.hass.async_add_executor_job(self.sub_device.update)
        except GatewayException as ex:
            raise UpdateFailed(
                f"Error fetching data from subdevice {self.sub_device.sid}: {ex}"
            ) from ex
