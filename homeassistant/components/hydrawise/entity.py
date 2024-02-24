"""Base classes for Hydrawise entities."""
from __future__ import annotations

from pydrawise.schema import Controller, Zone

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HydrawiseDataUpdateCoordinator


class HydrawiseEntity(CoordinatorEntity[HydrawiseDataUpdateCoordinator]):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HydrawiseDataUpdateCoordinator,
        description: EntityDescription,
        controller: Controller,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.controller = controller
        self.zone = zone
        self._device_id = str(controller.id if zone is None else zone.id)
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=controller.name if zone is None else zone.name,
            manufacturer=MANUFACTURER,
        )
        if zone is not None:
            self._attr_device_info["via_device"] = (DOMAIN, str(controller.id))
        self._update_attrs()

    def _update_attrs(self) -> None:
        """Update state attributes."""
        return  # pragma: no cover

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""
        self.controller = self.coordinator.data.controllers[self.controller.id]
        if self.zone:
            self.zone = self.coordinator.data.zones[self.zone.id]
        self._update_attrs()
        super()._handle_coordinator_update()
