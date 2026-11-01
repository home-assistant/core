"""Base entity for the Seafile integration."""

from typing import override

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LIBRARY_ID, DOMAIN
from .coordinator import SeafileDataUpdateCoordinator


class SeafileEntity(CoordinatorEntity[SeafileDataUpdateCoordinator]):
    """Base class for entities of a library."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SeafileDataUpdateCoordinator,
        subentry: ConfigSubentry,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity on the library device."""
        super().__init__(coordinator)
        self.entity_description = description
        self.library_id: str = subentry.data[CONF_LIBRARY_ID]
        self._attr_unique_id = f"{subentry.subentry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Seafile",
            model="Library",
            name=subentry.title,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the library still exists."""
        return super().available and self.library_id in self.coordinator.data.libraries
