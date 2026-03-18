"""Coordinator entity base class for CometBlue."""

import logging

from homeassistant.components import bluetooth
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import CometBlueDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


class CometBlueBluetoothEntity(CoordinatorEntity[CometBlueDataUpdateCoordinator]):
    """Coordinator entity for CometBlue."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CometBlueDataUpdateCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)
        # Full DeviceInfo is added to DeviceRegistry in __init__.py, so we only
        # set identifiers here to link the entity to the device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.address)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # As long the device is currently connectable via Bluetooth it is available, even if the last update failed.
        # This is because Bluetooth connectivity can be intermittent and a failed update doesn't necessarily mean the device is unavailable.
        # The BluetoothManager will check every 300s (same interval as DataUpdateCoordinator) if the device is still present and connectable.
        return bluetooth.async_address_present(
            self.hass, address=self.coordinator.address, connectable=True
        )
