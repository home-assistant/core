"""Common entity class for Version integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HOME_ASSISTANT
from .coordinator import VersionDataUpdateCoordinator


class VersionEntity(CoordinatorEntity[VersionDataUpdateCoordinator]):
    """Common entity class for Version integration."""

    _attr_device_info = DeviceInfo(
        name=f"{HOME_ASSISTANT} {DOMAIN.title()}",
        identifiers={(HOME_ASSISTANT, DOMAIN)},
        manufacturer=HOME_ASSISTANT,
        entry_type=DeviceEntryType.SERVICE,
    )

    def __init__(
        self,
        coordinator: VersionDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize version entities."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
