"""Base classes for Hydrawise entities."""

from typing import override

from pydrawise.schema import Controller, Sensor, Zone

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_ZONE
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
                MODEL_ZONE
                if zone_id is not None
                else controller.hardware.model.description
            ),
            manufacturer=MANUFACTURER,
        )
        if zone_id is not None:
            # Only zones get their own device; sensor entities share the
            # controller device, so linking them to the controller would create
            # a self-referential via_device.
            self._attr_device_info["via_device_id"] = (
                dr.async_get_device_id_by_identifier(
                    self.coordinator.hass,
                    (DOMAIN, str(controller.id)),
                    config_entry_id=self.coordinator.config_entry.entry_id,
                )
            )
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
    @override
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""
        # Guard against updates arriving after what the entity reads on has gone
        # but before the entity has been unsubscribed from the coordinator.
        data = self.coordinator.data
        if (
            self.controller.id not in data.controllers
            or (self.zone_id is not None and self.zone_id not in data.zones)
            or (self.sensor_id is not None and self.sensor_id not in data.sensors)
        ):
            return
        self.controller = data.controllers[self.controller.id]
        self._update_attrs()
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Set the entity availability."""
        return super().available and self.controller.online
