"""Coordinator for the Melnor integration."""

from datetime import timedelta
import logging

from melnor_bluetooth.device import Device

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MelnorDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Melnor data update coordinator."""

    _device: Device

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Melnor Bluetooth",
            update_interval=timedelta(seconds=5),
        )
        self._device = device

    async def _async_update_data(self):
        """Update the device state."""

        await self._device.fetch_state()
        return self._device
