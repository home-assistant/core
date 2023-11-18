"""Base entity for the Minecraft Server integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MinecraftServerType
from .const import DOMAIN
from .coordinator import MinecraftServerCoordinator

MANUFACTURER = "Mojang Studios"


class MinecraftServerEntity(CoordinatorEntity[MinecraftServerCoordinator]):
    """Representation of a Minecraft Server base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=f"Minecraft Server ({config_entry.data.get(CONF_TYPE, MinecraftServerType.JAVA_EDITION)})",
            name=coordinator.name,
            sw_version=f"{coordinator.data.version} ({coordinator.data.protocol_version})",
        )
