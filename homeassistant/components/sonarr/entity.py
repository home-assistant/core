"""Base Entity for Sonarr."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SonarrDataT, SonarrDataUpdateCoordinator


class SonarrEntity(CoordinatorEntity[SonarrDataUpdateCoordinator[SonarrDataT]]):
    """Defines a base Sonarr entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SonarrDataUpdateCoordinator[SonarrDataT],
        description: EntityDescription,
    ) -> None:
        """Initialize the Sonarr entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the application."""
        return DeviceInfo(
            configuration_url=self.coordinator.host_configuration.base_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=self.coordinator.system_version,
        )
