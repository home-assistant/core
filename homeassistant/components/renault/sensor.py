"""Support for Renault sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleChargingSettingsData,
    KamereonVehicleCockpitData,
    KamereonVehicleDataAttributes,
    KamereonVehicleHvacStatusData,
    KamereonVehicleLocationData,
    KamereonVehicleResStateData,
    KamereonVehicleTyrePressureData,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_utc, parse_datetime

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .renault_vehicle import RenaultVehicleProxy

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RenaultSensorEntityDescription[T: KamereonVehicleDataAttributes](
    SensorEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault sensor entities."""

    condition_lambda: Callable[[RenaultVehicleProxy], bool] | None = None
    requires_fuel: bool = False
    value_lambda: Callable[[RenaultSensor[T]], StateType | datetime]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultSensor[Any]] = [
        RenaultSensor(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
        and (not description.requires_fuel or vehicle.details.uses_fuel())
        and (not description.condition_lambda or description.condition_lambda(vehicle))
    ]
    async_add_entities(entities)


class RenaultSensor[T: KamereonVehicleDataAttributes](
    RenaultDataEntity[T], SensorEntity
):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSensorEntityDescription[T]

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of this entity."""
        return self.entity_description.value_lambda(self)


def _get_charging_power(
    entity: RenaultSensor[KamereonVehicleBatteryStatusData],
) -> StateType:
    """Return the charging_power of this entity."""
    if (data := entity.coordinator.data.chargingInstantaneousPower) is None:
        return None
    return data / 1000


def _get_charge_state_formatted(
    entity: RenaultSensor[KamereonVehicleBatteryStatusData],
) -> str | None:
    """Return the charging_status of this entity."""
    charging_status = entity.coordinator.data.get_charging_status()
    return charging_status.name.lower() if charging_status else None


def _get_plug_state_formatted(
    entity: RenaultSensor[KamereonVehicleBatteryStatusData],
) -> str | None:
    """Return the plug_status of this entity."""
    plug_status = entity.coordinator.data.get_plug_status()
    return plug_status.name.lower() if plug_status else None


def _get_rounded_value(value: float | None) -> int | None:
    """Return the rounded value of this entity."""
    if value is None:
        return None
    return round(value)


def _get_utc_value(value: str | None) -> datetime | None:
    """Return the UTC value of this entity."""
    if (value is None) or (original_dt := parse_datetime(value)) is None:
        return None
    return as_utc(original_dt)


def _get_charging_settings_mode_formatted(
    entity: RenaultSensor[KamereonVehicleChargingSettingsData],
) -> str | None:
    """Return the charging_settings mode of this entity."""
    charging_mode = entity.coordinator.data.mode
    return charging_mode.lower() if charging_mode else None


SENSOR_TYPES: tuple[RenaultSensorEntityDescription[Any], ...] = (
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_level",
        coordinator="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=lambda e: e.coordinator.data.batteryLevel,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="charge_state",
        coordinator="battery",
        translation_key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "not_in_charge",
            "waiting_for_a_planned_charge",
            "charge_ended",
            "waiting_for_current_charge",
            "energy_flap_opened",
            "charge_in_progress",
            "charge_error",
            "unavailable",
        ],
        value_lambda=_get_charge_state_formatted,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="charging_remaining_time",
        coordinator="battery",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="charging_remaining_time",
        value_lambda=lambda e: e.coordinator.data.chargingRemainingTime,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        # For vehicles that DO NOT report charging power in watts, this seems to
        # correspond to the maximum power that would be admissible by the car based
        # on the battery state, regardless of the type of charger.
        key="charging_power",
        condition_lambda=lambda a: not a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="admissible_charging_power",
        value_lambda=lambda e: e.coordinator.data.chargingInstantaneousPower,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        # For vehicles that DO report charging power in watts, this is the power
        # effectively being transferred to the car.
        key="charging_power",
        condition_lambda=lambda a: a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=_get_charging_power,
        translation_key="charging_power",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="plug_state",
        coordinator="battery",
        translation_key="plug_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "unplugged",
            "plugged",
            "plugged_waiting_for_charge",
            "plug_error",
            "plug_unknown",
        ],
        value_lambda=_get_plug_state_formatted,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_autonomy",
        coordinator="battery",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_autonomy",
        value_lambda=lambda e: e.coordinator.data.batteryAutonomy,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_available_energy",
        coordinator="battery",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        translation_key="battery_available_energy",
        value_lambda=lambda e: e.coordinator.data.batteryAvailableEnergy,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_temperature",
        coordinator="battery",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_temperature",
        value_lambda=lambda e: e.coordinator.data.batteryTemperature,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_last_activity",
        coordinator="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_lambda=lambda e: _get_utc_value(e.coordinator.data.timestamp),
        translation_key="battery_last_activity",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="mileage",
        coordinator="cockpit",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_lambda=lambda e: _get_rounded_value(e.coordinator.data.totalMileage),
        translation_key="mileage",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="fuel_autonomy",
        coordinator="cockpit",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=lambda e: _get_rounded_value(e.coordinator.data.fuelAutonomy),
        translation_key="fuel_autonomy",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="fuel_quantity",
        coordinator="cockpit",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        requires_fuel=True,
        value_lambda=lambda e: _get_rounded_value(e.coordinator.data.fuelQuantity),
        translation_key="fuel_quantity",
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outside_temperature",
        value_lambda=lambda e: e.coordinator.data.externalTemperature,
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="hvac_soc_threshold",
        coordinator="hvac_status",
        native_unit_of_measurement=PERCENTAGE,
        translation_key="hvac_soc_threshold",
        value_lambda=lambda e: e.coordinator.data.socThreshold,
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="hvac_last_activity",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        translation_key="hvac_last_activity",
        value_lambda=lambda e: _get_utc_value(e.coordinator.data.lastUpdateTime),
    ),
    RenaultSensorEntityDescription[KamereonVehicleLocationData](
        key="location_last_activity",
        coordinator="location",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        translation_key="location_last_activity",
        value_lambda=lambda e: _get_utc_value(e.coordinator.data.lastUpdateTime),
    ),
    RenaultSensorEntityDescription[KamereonVehicleResStateData](
        key="res_state",
        coordinator="res_state",
        translation_key="res_state",
        value_lambda=lambda e: e.coordinator.data.details,
    ),
    RenaultSensorEntityDescription[KamereonVehicleResStateData](
        key="res_state_code",
        coordinator="res_state",
        entity_registry_enabled_default=False,
        translation_key="res_state_code",
        value_lambda=lambda e: e.coordinator.data.code,
    ),
    RenaultSensorEntityDescription[KamereonVehicleChargingSettingsData](
        key="charging_settings_mode",
        coordinator="charging_settings",
        translation_key="charging_settings_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "always",
            "delayed",
            "scheduled",
        ],
        value_lambda=_get_charging_settings_mode_formatted,
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="front_left_pressure",
        coordinator="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="front_left_pressure",
        value_lambda=lambda e: e.coordinator.data.flPressure,
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="front_right_pressure",
        coordinator="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="front_right_pressure",
        value_lambda=lambda e: e.coordinator.data.frPressure,
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="rear_left_pressure",
        coordinator="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="rear_left_pressure",
        value_lambda=lambda e: e.coordinator.data.rlPressure,
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="rear_right_pressure",
        coordinator="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="rear_right_pressure",
        value_lambda=lambda e: e.coordinator.data.rrPressure,
    ),
)
