"""Base entity for the Eve Online integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EveOnlineCoordinator


class EveOnlineCharacterEntity(CoordinatorEntity[EveOnlineCoordinator]):
    """Base entity for an Eve Online character."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EveOnlineCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.character_id}_{key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(coordinator.character_id))},
            manufacturer="CCP Games",
            name=coordinator.character_name,
        )
