"""Base entity for Nice G.O."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NiceGODevice, NiceGOUpdateCoordinator


class NiceGOEntity(CoordinatorEntity[NiceGOUpdateCoordinator]):
    """Common base for Nice G.O. entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NiceGOUpdateCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = device_id
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            sw_version=coordinator.data[device_id].fw_version,
        )

    @property
    def data(self) -> NiceGODevice:
        """Return the Nice G.O. device."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.data.connected
