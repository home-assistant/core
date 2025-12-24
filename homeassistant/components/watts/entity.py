"""Base entity for Watts Vision integration."""

from __future__ import annotations

from visionpluspython.models import ThermostatDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WattsVisionThermostatCoordinator


class WattsVisionThermostatEntity(CoordinatorEntity[WattsVisionThermostatCoordinator]):
    """Base entity for Watts Vision thermostat devices."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WattsVisionThermostatCoordinator, device_id: str
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator, context=device_id)
        self.device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self.thermostat.device_name,
            manufacturer="Watts",
            model=f"Vision+ {self.thermostat.device_type}",
            suggested_area=self.thermostat.room_name,
        )

    @property
    def thermostat(self) -> ThermostatDevice:
        """Return the thermostat device from the coordinator data."""
        return self.coordinator.data.thermostat

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.thermostat.is_online
