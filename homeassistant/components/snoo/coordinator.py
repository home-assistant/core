"""Support for Anova Coordinators."""

import logging

from python_snoo.containers import SnooData, SnooDevice
from python_snoo.snoo import Snoo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SnooCoordinator(DataUpdateCoordinator[SnooData]):
    """Snoo custom coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device: SnooDevice, snoo: Snoo) -> None:
        """Set up Snoo Coordinator."""
        super().__init__(
            hass,
            name=device.name,
            logger=_LOGGER,
        )
        self.device_unique_id = device.serialNumber
        self.device = device
        self.device_info: DeviceInfo | None = None
        self.sensor_data_set: bool = False
        self.snoo = snoo

    async def setup(self) -> None:
        """Perform setup needed on every coordintaor creation."""
        await self.snoo.subscribe(self.device, self.async_set_updated_data)
        # After we subscribe - get the status so that we have something to start with.
        # We only need to do this once. The device will auto update otherwise.
        await self.snoo.get_status(self.device)
