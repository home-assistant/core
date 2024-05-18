"""Base classes for Hydrawise entities."""

from __future__ import annotations

from pydrawise.schema import Controller, Sensor, Zone

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
        *,
        zone_id: int | None = None,
        sensor_id: int | None = None,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.controller = controller
        self.zone_id = zone_id
        self.sensor_id = sensor_id
        self._device_id = str(zone_id) if zone_id is not None else str(controller.id)
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self.zone.name if zone_id is not None else controller.name,
            model=(
                "Zone" if zone_id is not None else controller.hardware.model.description
            ),
            manufacturer=MANUFACTURER,
        )
        if zone_id is not None or sensor_id is not None:
            self._attr_device_info["via_device"] = (DOMAIN, str(controller.id))
        self._update_attrs()

    @property
    def zone(self) -> Zone:
        """Return the entity zone."""
        assert self.zone_id is not None  # needed for mypy
        return self.coordinator.data.zones[self.zone_id]

    @property
    def sensor(self) -> Sensor:
        """Return the entity sensor."""
        assert self.sensor_id is not None  # needed for mypy
        return self.coordinator.data.sensors[self.sensor_id]

    def _update_attrs(self) -> None:
        """Update state attributes."""
        return  # pragma: no cover

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""
        self.controller = self.coordinator.data.controllers[self.controller.id]
        self._update_attrs()
        super()._handle_coordinator_update()
