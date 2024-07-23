"""Base entity for Monzo."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MonzoCoordinator, MonzoData


class MonzoBaseEntity(CoordinatorEntity[MonzoCoordinator]):
    """Common base for Monzo entities."""

    _attr_attribution = "Data provided by Monzo"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MonzoCoordinator,
        index: int,
        device_model: str,
        data_accessor: Callable[[MonzoData], list[dict[str, Any]]],
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.index = index
        self._data_accessor = data_accessor

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(self.data["id"]))},
            manufacturer="Monzo",
            model=device_model,
            name=self.data["name"],
        )

    @property
    def data(self) -> dict[str, Any]:
        """Shortcut to access coordinator data for the entity."""
        return self._data_accessor(self.coordinator.data)[self.index]
