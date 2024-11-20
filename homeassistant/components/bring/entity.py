"""Base entity for the Bring! integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BringData, BringDataUpdateCoordinator


class BringBaseEntity(CoordinatorEntity[BringDataUpdateCoordinator]):
    """Bring base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BringDataUpdateCoordinator,
        bring_list: BringData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._list_uuid = bring_list["listUuid"]

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=bring_list["name"],
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.unique_id}_{self._list_uuid}")
            },
            manufacturer="Bring! Labs AG",
            model="Bring! Grocery Shopping List",
            configuration_url=f"https://web.getbring.com/app/lists/{list(self.coordinator.data.keys()).index(self._list_uuid)}",
        )
