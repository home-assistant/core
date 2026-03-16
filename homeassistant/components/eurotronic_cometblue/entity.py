"""Coordinator entity base class for CometBlue."""

import logging

from homeassistant.components import bluetooth
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .const import MAX_RETRIES
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
        return (
            self.coordinator.failed_update_count < MAX_RETRIES
            and bluetooth.async_address_present(
                self.hass, self.coordinator.address, True
            )
        )
