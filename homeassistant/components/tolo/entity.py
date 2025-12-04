"""Component to control TOLO Sauna/Steam Bath."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ToloConfigEntry, ToloSaunaUpdateCoordinator


class ToloSaunaCoordinatorEntity(CoordinatorEntity[ToloSaunaUpdateCoordinator]):
    """CoordinatorEntity for TOLO Sauna."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ToloConfigEntry
    ) -> None:
        """Initialize ToloSaunaCoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            name="TOLO Sauna",
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="SteamTec",
            model=self.coordinator.data.status.model.name.capitalize(),
        )
