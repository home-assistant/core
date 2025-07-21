"""Base entity for PlayStation Network Integration."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaystationNetworkUserDataCoordinator


class PlaystationNetworkServiceEntity(
    CoordinatorEntity[PlaystationNetworkUserDataCoordinator]
):
    """Common entity class for PlayStationNetwork Service entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlaystationNetworkUserDataCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize PlayStation Network Service Entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.data.username,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Sony Interactive Entertainment",
        )
