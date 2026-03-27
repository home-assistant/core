"""Base entity classes for the Eve Online integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EveOnlineCoordinator


class EveOnlineEntity(CoordinatorEntity[EveOnlineCoordinator]):
    """Base class for all Eve Online entities."""

    _attr_has_entity_name = True


class EveOnlineServerEntity(EveOnlineEntity):
    """Base class for Eve Online server (Tranquility) entities."""

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        key: str,
    ) -> None:
        """Initialize server entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "tranquility")},
            name="Eve Online (Tranquility)",
            manufacturer="CCP Games",
            model="ESI API",
            sw_version=coordinator.data.server_status.server_version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://esi.evetech.net/ui/",
        )


class EveOnlineCharacterEntity(EveOnlineEntity):
    """Base class for Eve Online character entities."""

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        key: str,
    ) -> None:
        """Initialize character entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.character_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.character_id))},
            name=coordinator.character_name,
            manufacturer="CCP Games",
            model="Eve Online Character",
            entry_type=DeviceEntryType.SERVICE,
            via_device=(DOMAIN, "tranquility"),
            configuration_url=(
                f"https://evewho.com/character/{coordinator.character_id}"
            ),
        )
