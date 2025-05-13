"""Volvo sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from volvocarsapi.models import (
    VolvoCarsApiBaseModel,
    VolvoCarsValue,
    VolvoCarsValueField,
    VolvoCarsVehicle,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_BATTERY_CAPACITY
from .coordinator import VolvoConfigEntry, VolvoDataCoordinator
from .entity import VolvoEntity, VolvoEntityDescription, value_to_translation_key

PARALLEL_UPDATES = 0

# Entities having an "unknown" value should report None as the state
_UNKNOWN_VALUES = [
    "UNSPECIFIED",
    "CONNECTION_STATUS_UNSPECIFIED",
    "CHARGING_SYSTEM_UNSPECIFIED",
]


@dataclass(frozen=True, kw_only=True)
class VolvoSensorDescription(VolvoEntityDescription, SensorEntityDescription):
    """Describes a Volvo sensor entity."""

    value_fn: Callable[[VolvoCarsValue, VolvoConfigEntry], Any] | None = None
    available_fn: Callable[[VolvoCarsVehicle], bool] = lambda vehicle: True


def _availability_status(field: VolvoCarsValue, _: VolvoConfigEntry) -> str:
    reason = field.get("unavailable_reason")
    return reason if reason else str(field.value)


def _calculate_time_to_service(field: VolvoCarsValue, _: VolvoConfigEntry) -> int:
    value = int(field.value)

    # Always express value in days
    if isinstance(field, VolvoCarsValueField) and field.unit == "months":
        return value * 30

    return value


_DESCRIPTIONS: tuple[VolvoSensorDescription, ...] = (
    # command-accessibility endpoint
    VolvoSensorDescription(
        key="availability",
        translation_key="availability",
        api_field="availabilityStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "car_in_use",
            "no_internet",
            "power_saving_mode",
            "unspecified",
        ],
        value_fn=_availability_status,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption",
        translation_key="average_energy_consumption",
        api_field="averageEnergyConsumption",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_automatic",
        translation_key="average_energy_consumption_automatic",
        api_field="averageEnergyConsumptionAutomatic",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_charge",
        translation_key="average_energy_consumption_charge",
        api_field="averageEnergyConsumptionSinceCharge",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption",
        translation_key="average_fuel_consumption",
        api_field="averageFuelConsumption",
        native_unit_of_measurement="l/100 km",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_combustion_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption_automatic",
        translation_key="average_fuel_consumption_automatic",
        api_field="averageFuelConsumptionAutomatic",
        native_unit_of_measurement="l/100 km",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_combustion_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed",
        translation_key="average_speed",
        api_field="averageSpeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed_automatic",
        translation_key="average_speed_automatic",
        api_field="averageSpeedAutomatic",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # vehicle endpoint
    VolvoSensorDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        api_field=DATA_BATTERY_CAPACITY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # fuel & recharge-status endpoint
    VolvoSensorDescription(
        key="battery_charge_level",
        translation_key="battery_charge_level",
        api_field="batteryChargeLevel",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # recharge-status endpoint
    VolvoSensorDescription(
        key="charging_connection_status",
        translation_key="charging_connection_status",
        api_field="chargingConnectionStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "connection_status_connected_ac",
            "connection_status_connected_dc",
            "connection_status_disconnected",
            "connection_status_fault",
            "connection_status_unspecified",
        ],
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # recharge-status endpoint
    VolvoSensorDescription(
        key="charging_current_limit",
        translation_key="charging_current_limit",
        api_field="chargingCurrentLimit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # recharge-status endpoint
    VolvoSensorDescription(
        key="charging_system_status",
        translation_key="charging_system_status",
        api_field="chargingSystemStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "charging_system_charging",
            "charging_system_done",
            "charging_system_fault",
            "charging_system_idle",
            "charging_system_scheduled",
            "charging_system_unspecified",
        ],
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="distance_to_empty_battery",
        translation_key="distance_to_empty_battery",
        api_field="distanceToEmptyBattery",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="distance_to_empty_tank",
        translation_key="distance_to_empty_tank",
        api_field="distanceToEmptyTank",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_combustion_engine(),
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="distance_to_service",
        translation_key="distance_to_service",
        api_field="distanceToService",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="engine_time_to_service",
        translation_key="engine_time_to_service",
        api_field="engineHoursToService",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    # recharge-status endpoint
    VolvoSensorDescription(
        key="estimated_charging_time",
        translation_key="estimated_charging_time",
        api_field="estimatedChargingTime",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # fuel endpoint
    VolvoSensorDescription(
        key="fuel_amount",
        translation_key="fuel_amount",
        api_field="fuelAmount",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda vehicle: vehicle.has_combustion_engine(),
    ),
    # odometer endpoint
    VolvoSensorDescription(
        key="odometer",
        translation_key="odometer",
        api_field="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
    ),
    # recharge-status endpoint
    VolvoSensorDescription(
        key="target_battery_charge_level",
        translation_key="target_battery_charge_level",
        api_field="targetBatteryChargeLevel",
        native_unit_of_measurement=PERCENTAGE,
        available_fn=lambda vehicle: vehicle.has_battery_engine(),
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="time_to_service",
        translation_key="time_to_service",
        api_field="timeToService",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=_calculate_time_to_service,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="trip_meter_automatic",
        translation_key="trip_meter_automatic",
        api_field="tripMeterAutomatic",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="trip_meter_manual",
        translation_key="trip_meter_manual",
        api_field="tripMeterManual",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    coordinator = entry.runtime_data
    items = [
        VolvoSensor(coordinator, description)
        for description in _DESCRIPTIONS
        if description.api_field in coordinator.data
        and description.available_fn(coordinator.vehicle)
    ]

    async_add_entities(items)


class VolvoSensor(VolvoEntity, SensorEntity):
    """Volvo sensor."""

    entity_description: VolvoSensorDescription

    def __init__(
        self,
        coordinator: VolvoDataCoordinator,
        description: VolvoSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        assert isinstance(api_field, VolvoCarsValue)

        native_value = (
            api_field.value
            if self.entity_description.value_fn is None
            else self.entity_description.value_fn(
                api_field, self.coordinator.config_entry
            )
        )

        if self.device_class == SensorDeviceClass.ENUM:
            native_value = str(native_value)
            native_value = (
                value_to_translation_key(native_value)
                if native_value.upper() not in _UNKNOWN_VALUES
                else None
            )

        self._attr_native_value = native_value
