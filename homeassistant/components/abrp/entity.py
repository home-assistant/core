"""Base entity for the A Better Routeplanner integration."""

from typing import override

from aioabrp import Telemetry

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AbrpConfigEntry, AbrpTelemetryCoordinator


class AbrpVehicleEntity(CoordinatorEntity[AbrpTelemetryCoordinator]):
    """An entity fed by one vehicle's streamed telemetry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AbrpTelemetryCoordinator,
        entry: AbrpConfigEntry,
        vehicle_id: int,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        scope = f"{entry.unique_id}_{vehicle_id}"
        self._attr_unique_id = f"{scope}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, scope)},
        )

    @property
    def telemetry(self) -> Telemetry | None:
        """Return this vehicle's merged telemetry, if any has arrived."""
        return self.coordinator.data.get(self._vehicle_id)

    @override
    async def async_update(self) -> None:
        """Make update_entity a no-op; values arrive through the stream."""
