"""Support for Autoskope sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autoskope_client.constants import MANUFACTURER
from autoskope_client.models import Vehicle
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricPotential, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutoskopeConfigEntry, AutoskopeDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class AutoskopeSensorEntityDescription(SensorEntityDescription):
    """Describes an Autoskope sensor entity."""

    value_fn: Callable[[Vehicle], StateType] = lambda x: None


SENSOR_DESCRIPTIONS: tuple[AutoskopeSensorEntityDescription, ...] = (
    AutoskopeSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda vehicle: vehicle.battery_voltage,
    ),
    AutoskopeSensorEntityDescription(
        key="external_voltage",
        translation_key="external_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda vehicle: vehicle.external_voltage,
    ),
    AutoskopeSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: vehicle.position.speed if vehicle.position else None,
    ),
    AutoskopeSensorEntityDescription(
        key="gps_quality",
        translation_key="gps_quality",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda vehicle: vehicle.gps_quality,
    ),
    AutoskopeSensorEntityDescription(
        key="gps_accuracy",
        translation_key="gps_accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: (
            max(5, int(vehicle.gps_quality * 5.0))
            if vehicle.gps_quality and vehicle.gps_quality > 0
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutoskopeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Autoskope sensor entities."""
    coordinator = entry.runtime_data
    tracked_vehicles: set[str] = set()

    def update_entities() -> None:
        """Update entities based on coordinator data."""
        if not coordinator.data:
            return

        new_entities: list[AutoskopeSensor] = []
        current_vehicles = set(coordinator.data.keys())

        for vehicle_id in current_vehicles - tracked_vehicles:
            if vehicle_id in coordinator.data:
                new_entities.extend(
                    AutoskopeSensor(coordinator, vehicle_id, description)
                    for description in SENSOR_DESCRIPTIONS
                )
                tracked_vehicles.add(vehicle_id)

        if new_entities:
            async_add_entities(new_entities)

    # Register listener and update immediately
    entry.async_on_unload(coordinator.async_add_listener(update_entities))
    update_entities()


class AutoskopeSensor(CoordinatorEntity[AutoskopeDataUpdateCoordinator], SensorEntity):
    """Representation of an Autoskope sensor."""

    entity_description: AutoskopeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AutoskopeDataUpdateCoordinator,
        vehicle_id: str,
        description: AutoskopeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_{description.key}"

        # Set device info in constructor
        vehicle_data = coordinator.data.get(vehicle_id) if coordinator.data else None
        if vehicle_data:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, str(vehicle_data.id))},
                name=vehicle_data.name,
                manufacturer=MANUFACTURER,
                model=vehicle_data.model,
                serial_number=vehicle_data.imei,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._vehicle_id in self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or self._vehicle_id not in self.coordinator.data:
            return None

        vehicle = self.coordinator.data[self._vehicle_id]
        return self.entity_description.value_fn(vehicle)
