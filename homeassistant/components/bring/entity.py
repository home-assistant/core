"""Base entity for the Bring! integration."""

from __future__ import annotations

from bring_api import BringList

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BringDataUpdateCoordinator


class BringBaseEntity(CoordinatorEntity[BringDataUpdateCoordinator]):
    """Bring base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringList,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, bring_list.listUuid)

        self._list_uuid = bring_list.listUuid

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=bring_list.name,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.unique_id}_{self._list_uuid}")
            },
            manufacturer="Bring! Labs AG",
            model="Bring! Grocery Shopping List",
            configuration_url=f"https://web.getbring.com/app/lists/{list(self.coordinator.lists).index(bring_list)}",
        )
