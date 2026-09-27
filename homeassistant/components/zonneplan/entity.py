"""Base entity for Zonneplan."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZonneplanCoordinator


class ZonneplanEntity(CoordinatorEntity[ZonneplanCoordinator]):
    """Base entity for Zonneplan."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ZonneplanCoordinator, entity_description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.data.account.user_account.uuid}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Zonneplan",
            entry_type=DeviceEntryType.SERVICE,
        )
