"""Base entity for Withings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class MonzoBaseEntity(CoordinatorEntity):
    """Common base for Monzo entities."""

    _attr_attribution = "Data provided by Monzo"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        index: int,
        device_model: str,
        data_accessor: Callable[
            [dict[str, list[dict[str, Any]]]], list[dict[str, Any]]
        ],
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.index = index
        self._data_accessor = data_accessor

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.data["id"]))},
            manufacturer="Monzo",
            model=device_model,
            name=self.data["name"],
        )

    @property
    def data(self) -> dict[str, Any]:
        """Shortcut to access coordinator data for the entity."""
        return self._data_accessor(self.coordinator.data)[self.index]
