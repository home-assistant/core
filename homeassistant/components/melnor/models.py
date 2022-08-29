"""Melnor integration models."""

from datetime import timedelta
import logging

from melnor_bluetooth.device import Device

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

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


class MelnorBluetoothBaseEntity(CoordinatorEntity[MelnorDataUpdateCoordinator]):
    """Base class for melnor entities."""

    _device: Device

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
    ) -> None:
        """Initialize a melnor base entity."""
        super().__init__(coordinator)

        self._device = coordinator.data

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            manufacturer="Melnor",
            model=self._device.model,
            name=self._device.name,
        )
        self._attr_name = self._device.name
        self._attr_unique_id = self._device.mac

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.data
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_connected
