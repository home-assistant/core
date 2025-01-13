"""Base entity for Sabnzbd."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SabnzbdUpdateCoordinator


class SabnzbdEntity(CoordinatorEntity[SabnzbdUpdateCoordinator]):
    """Defines a base Sabnzbd entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SabnzbdUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            sw_version=coordinator.data["version"],
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )
