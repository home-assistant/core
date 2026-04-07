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

    data_key: str
    condition_lambda: Callable[[RenaultVehicleProxy], bool] | None = None
    requires_fuel: bool = False
    value_lambda: Callable[[RenaultSensor[T]], StateType | datetime] | None = None


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
    def data(self) -> StateType:
        """Return the state of this entity."""
        return self._get_data_attr(self.entity_description.data_key)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of this entity."""
        if self.data is None:
            return None
        if self.entity_description.value_lambda is None:
            return self.data
        return self.entity_description.value_lambda(self)


SENSOR_TYPES: tuple[RenaultSensorEntityDescription[Any], ...] = (
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_level",
        coordinator="battery",
        data_key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="charge_state",
        coordinator="battery",
        data_key="chargingStatus",
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
        value_lambda=lambda e: (
            charging_status.name.lower()
            if (charging_status := e.coordinator.data.get_charging_status())
            else None
        ),
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="charging_remaining_time",
        coordinator="battery",
        data_key="chargingRemainingTime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="charging_remaining_time",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        # For vehicles that DO NOT report charging power in watts, this seems to
        # correspond to the maximum power that would be admissible by the car based
        # on the battery state, regardless of the type of charger.
        key="charging_power",
        condition_lambda=lambda a: not a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="admissible_charging_power",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        # For vehicles that DO report charging power in watts, this is the power
        # effectively being transferred to the car.
        key="charging_power",
        condition_lambda=lambda a: a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=lambda e: (
            power / 1000
            if (power := e.coordinator.data.chargingInstantaneousPower) is not None
            else None
        ),
        translation_key="charging_power",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="plug_state",
        coordinator="battery",
        data_key="plugStatus",
        translation_key="plug_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "unplugged",
            "plugged",
            "plugged_waiting_for_charge",
            "plug_error",
            "plug_unknown",
        ],
        value_lambda=lambda e: (
            plug_status.name.lower()
            if (plug_status := e.coordinator.data.get_plug_status())
            else None
        ),
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_autonomy",
        coordinator="battery",
        data_key="batteryAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_autonomy",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_available_energy",
        coordinator="battery",
        data_key="batteryAvailableEnergy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        translation_key="battery_available_energy",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_temperature",
        coordinator="battery",
        data_key="batteryTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_temperature",
    ),
    RenaultSensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="battery_last_activity",
        coordinator="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="timestamp",
        entity_registry_enabled_default=False,
        value_lambda=lambda e: (
            as_utc(dt)
            if (ts := e.coordinator.data.timestamp) and (dt := parse_datetime(ts))
            else None
        ),
        translation_key="battery_last_activity",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="mileage",
        coordinator="cockpit",
        data_key="totalMileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_lambda=lambda e: (
            round(mileage)
            if (mileage := e.coordinator.data.totalMileage) is not None
            else None
        ),
        translation_key="mileage",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="fuel_autonomy",
        coordinator="cockpit",
        data_key="fuelAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=lambda e: (
            round(fuel_autonomy)
            if (fuel_autonomy := e.coordinator.data.fuelAutonomy) is not None
            else None
        ),
        translation_key="fuel_autonomy",
    ),
    RenaultSensorEntityDescription[KamereonVehicleCockpitData](
        key="fuel_quantity",
        coordinator="cockpit",
        data_key="fuelQuantity",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        requires_fuel=True,
        value_lambda=lambda e: (
            round(fuel_quantity)
            if (fuel_quantity := e.coordinator.data.fuelQuantity) is not None
            else None
        ),
        translation_key="fuel_quantity",
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TEMPERATURE,
        data_key="externalTemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outside_temperature",
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="hvac_soc_threshold",
        coordinator="hvac_status",
        data_key="socThreshold",
        native_unit_of_measurement=PERCENTAGE,
        translation_key="hvac_soc_threshold",
    ),
    RenaultSensorEntityDescription[KamereonVehicleHvacStatusData](
        key="hvac_last_activity",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_registry_enabled_default=False,
        translation_key="hvac_last_activity",
        value_lambda=lambda e: (
            as_utc(dt)
            if (ts := e.coordinator.data.lastUpdateTime) and (dt := parse_datetime(ts))
            else None
        ),
    ),
    RenaultSensorEntityDescription[KamereonVehicleLocationData](
        key="location_last_activity",
        coordinator="location",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_registry_enabled_default=False,
        translation_key="location_last_activity",
        value_lambda=lambda e: (
            as_utc(dt)
            if (ts := e.coordinator.data.lastUpdateTime) and (dt := parse_datetime(ts))
            else None
        ),
    ),
    RenaultSensorEntityDescription[KamereonVehicleResStateData](
        key="res_state",
        coordinator="res_state",
        data_key="details",
        translation_key="res_state",
    ),
    RenaultSensorEntityDescription[KamereonVehicleResStateData](
        key="res_state_code",
        coordinator="res_state",
        data_key="code",
        entity_registry_enabled_default=False,
        translation_key="res_state_code",
    ),
    RenaultSensorEntityDescription[KamereonVehicleChargingSettingsData](
        key="charging_settings_mode",
        coordinator="charging_settings",
        data_key="mode",
        translation_key="charging_settings_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "always",
            "delayed",
            "scheduled",
        ],
        value_lambda=lambda e: (
            charging_mode.lower()
            if (charging_mode := e.coordinator.data.mode)
            else None
        ),
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="front_left_pressure",
        coordinator="pressure",
        data_key="flPressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="front_left_pressure",
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="front_right_pressure",
        coordinator="pressure",
        data_key="frPressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="front_right_pressure",
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="rear_left_pressure",
        coordinator="pressure",
        data_key="rlPressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="rear_left_pressure",
    ),
    RenaultSensorEntityDescription[KamereonVehicleTyrePressureData](
        key="rear_right_pressure",
        coordinator="pressure",
        data_key="rrPressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="rear_right_pressure",
    ),
)
