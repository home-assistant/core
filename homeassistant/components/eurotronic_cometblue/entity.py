"""Update coordinator for CometBlue."""

from datetime import timedelta
import logging

from homeassistant.components import bluetooth
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MAX_RETRIES
from .coordinator import CometBlueDataUpdateCoordinator

SCAN_INTERVAL = timedelta(minutes=5)
LOGGER = logging.getLogger(__name__)


class CometBlueBluetoothEntity(CoordinatorEntity[CometBlueDataUpdateCoordinator]):
    """Coordinator entity for CometBlue."""

    coordinator: CometBlueDataUpdateCoordinator
    _attr_has_entity_name = True

    def __init__(self, coordinator: CometBlueDataUpdateCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.failed_update_count < MAX_RETRIES
            and bluetooth.async_address_present(
                self.hass, self.coordinator.address, True
            )
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
