"""Base entity for the Minecraft Server integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MinecraftServerCoordinator


class MinecraftServerEntity(CoordinatorEntity[MinecraftServerCoordinator]):
    """Representation of a Minecraft Server base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer=MANUFACTURER,
            model=f"Minecraft Server ({coordinator.data.version})",
            name=coordinator.name,
            sw_version=str(coordinator.data.protocol_version),
        )
