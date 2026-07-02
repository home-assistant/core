"""Base entity for ALLNET."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AllnetDataUpdateCoordinator


class AllnetEntity(CoordinatorEntity[AllnetDataUpdateCoordinator]):
    """Base class for ALLNET entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AllnetDataUpdateCoordinator,
        channel_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._channel_id = channel_id
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return True if coordinator is up and the channel has a valid value."""
        if not super().available:
            return False
        channel = self.coordinator.data.get(self._channel_id)
        return channel is not None and channel.value is not None
