"""Sensor entities for WeConnect integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from weconnect.weconnect import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WeConnectConfigEntry
from .coordinator import WeConnectCoordinator
from .entity import WeConnectEntity
from .utils import get_domain, get_electric_engine, get_fuel_engine


@dataclass(frozen=True)
class WeConnectSensorDescription(SensorEntityDescription):
    """Describes WeConnect sensor."""

    value: Callable[[Vehicle], Any] | None = None
    is_available: Callable[[Vehicle], bool] = lambda v: True


GENERIC_SENSORS = [
    WeConnectSensorDescription(
        key="mileage",
        translation_key="mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda v: d.odometer.value
        if (d := get_domain(v, "measurements", "odometerStatus")) is not None
        else None,
    ),
    WeConnectSensorDescription(
        key="inspection_due_days",
        translation_key="inspection_due_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value=lambda v: d.inspectionDue_days.value
        if (d := get_domain(v, "vehicleHealthInspection", "maintenanceStatus"))
        is not None
        else None,
    ),
    WeConnectSensorDescription(
        key="inspection_due_range",
        translation_key="inspection_due_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: d.inspectionDue_km.value
        if (d := get_domain(v, "vehicleHealthInspection", "maintenanceStatus"))
        is not None
        else None,
    ),
    WeConnectSensorDescription(
        key="remaining_range",
        translation_key="remaining_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: d.totalRange_km.value
        if (d := get_domain(v, "fuelStatus", "rangeStatus")) is not None
        else None,
    ),
]

FUEL_SENSORS = [
    WeConnectSensorDescription(
        key="fuel_remaining_percentage",
        translation_key="fuel_remaining_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: engine.currentFuelLevel_pct.value
        if (engine := get_fuel_engine(v)) is not None
        else None,
        is_available=lambda v: get_fuel_engine(v) is not None,
    ),
    WeConnectSensorDescription(
        key="fuel_remaining_range",
        translation_key="fuel_remaining_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: engine.remainingRange_km.value
        if (engine := get_fuel_engine(v)) is not None
        else None,
        is_available=lambda v: get_fuel_engine(v) is not None,
    ),
]

BATTERY_SENSORS = [
    WeConnectSensorDescription(
        key="battery_remaining_percentage",
        translation_key="battery_remaining_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: engine.currentSOC_pct.value
        if (engine := get_electric_engine(v)) is not None
        else None,
        is_available=lambda v: get_electric_engine(v) is not None,
    ),
    WeConnectSensorDescription(
        key="battery_remaining_range",
        translation_key="battery_remaining_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda v: engine.remainingRange_km.value
        if (engine := get_electric_engine(v)) is not None
        else None,
        is_available=lambda v: get_electric_engine(v) is not None,
    ),
]


class WeConnectSensor(WeConnectEntity, SensorEntity):
    """Sensor entity for WeConnect integration."""

    entity_description: WeConnectSensorDescription

    def __init__(
        self,
        coordinator: WeConnectCoordinator,
        vehicle: Vehicle,
        description: WeConnectSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle)

        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor's value."""
        return (
            self.entity_description.value(self.vehicle)
            if self.entity_description.value
            else None
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WeConnect sensor entities."""
    coordinator = config_entry.runtime_data.coordinator

    entities = []
    sensor_categories = [GENERIC_SENSORS, FUEL_SENSORS, BATTERY_SENSORS]

    for sensors in sensor_categories:
        entities.extend(
            [
                WeConnectSensor(coordinator, vehicle, description)
                for vehicle in coordinator.vehicles
                for description in sensors
                if description.is_available(vehicle)
            ]
        )

    async_add_entities(entities)
