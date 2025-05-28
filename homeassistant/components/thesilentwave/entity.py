"""Base entity for TheSilentWave integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TheSilentWaveCoordinator
from .const import DOMAIN


class TheSilentWaveEntity(CoordinatorEntity):
    """Base entity class for TheSilentWave integration."""

    _attr_has_entity_name = (
        True  # This makes the entity use the device name as a prefix.
    )

    def __init__(self, coordinator: TheSilentWaveCoordinator, entry_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_should_poll = True
        # Name property will be handled by the specific entity class.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self.coordinator.device_name,
            manufacturer="TheSilentWave",
        )
