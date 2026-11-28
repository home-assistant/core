"""Base entity for the Ablago integration."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AblagoCounterCoordinator


class AblagoEntity(CoordinatorEntity[AblagoCounterCoordinator]):
    """One device per config entry, that is per person and Ablago."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AblagoCounterCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        # A counters-only key cannot read the Ablago version or whom the key belongs to.
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Ablago",
            name=entry.title,
            configuration_url=entry.data[CONF_URL],
        )
