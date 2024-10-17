"""The Radarr component."""

from __future__ import annotations

from typing import cast

from homeassistant.const import ATTR_SW_VERSION
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import RadarrDataUpdateCoordinator, StatusDataUpdateCoordinator, T


class RadarrEntity(CoordinatorEntity[RadarrDataUpdateCoordinator[T]]):
    """Defines a base Radarr entity."""

    _attr_has_entity_name = True
    coordinator: RadarrDataUpdateCoordinator[T]

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator[T],
        description: EntityDescription,
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Radarr instance."""
        device_info = DeviceInfo(
            configuration_url=self.coordinator.host_configuration.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=self.coordinator.config_entry.title,
        )
        if isinstance(self.coordinator, StatusDataUpdateCoordinator):
            device_info[ATTR_SW_VERSION] = cast(
                StatusDataUpdateCoordinator, self.coordinator
            ).data.version
        return device_info
