"""Base entity classes for the Eve Online integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import _EveOnlineBaseCoordinator


class EveOnlineCharacterEntity[_CoordT: _EveOnlineBaseCoordinator[Any]](
    CoordinatorEntity[_CoordT]
):
    """Base class for all Eve Online character entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _CoordT,
        key: str,
    ) -> None:
        """Initialize character entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.character_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.character_id))},
            name=coordinator.character_name,
            manufacturer="CCP Games",
            model="Eve Online Character",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=(
                f"https://evewho.com/character/{coordinator.character_id}"
            ),
        )
