"""Base entity for Monzo."""

from collections.abc import Callable
from typing import Any, override

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
        resource_id: str,
        device_model: str,
        data_accessor: Callable[[MonzoData], dict[str, dict[str, Any]]],
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._resource_id = resource_id
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
        return self._data_accessor(self.coordinator.data)[self._resource_id]

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self._resource_id in self._data_accessor(
            self.coordinator.data
        )
