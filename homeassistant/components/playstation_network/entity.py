"""Base entity for PlayStation Network Integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlayStationNetworkBaseCoordinator
from .helpers import PlaystationNetworkData


class PlaystationNetworkServiceEntity(
    CoordinatorEntity[PlayStationNetworkBaseCoordinator]
):
    """Common entity class for PlayStationNetwork Service entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlayStationNetworkBaseCoordinator,
        entity_description: EntityDescription,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize PlayStation Network Service Entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.entity_description = entity_description
        self.subentry = subentry
        unique_id = (
            subentry.unique_id
            if subentry is not None and subentry.unique_id
            else coordinator.config_entry.unique_id
        )

        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=(
                coordinator.data.username
                if isinstance(coordinator.data, PlaystationNetworkData)
                else coordinator.psn.user.online_id
            ),
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Sony Interactive Entertainment",
        )
        if subentry:
            self._attr_device_info.update(
                DeviceInfo(via_device=(DOMAIN, coordinator.config_entry.unique_id))
            )
