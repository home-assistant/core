"""Support for Renault sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, cast

from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleCockpitData,
    KamereonVehicleHvacStatusData,
    KamereonVehicleLocationData,
    KamereonVehicleResStateData,
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
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_utc, parse_datetime

from . import RenaultConfigEntry
from .coordinator import T
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .renault_vehicle import RenaultVehicleProxy

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RenaultSensorEntityDescription(
    SensorEntityDescription, RenaultDataEntityDescription, Generic[T]
):
    """Class describing Renault sensor entities."""

    data_key: str
    entity_class: type[RenaultSensor[T]]
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
        description.entity_class(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
        and (not description.requires_fuel or vehicle.details.uses_fuel())
        and (not description.condition_lambda or description.condition_lambda(vehicle))
    ]
    async_add_entities(entities)


class RenaultSensor(RenaultDataEntity[T], SensorEntity):
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


def _get_charging_power(entity: RenaultSensor[T]) -> StateType:
    """Return the charging_power of this entity."""
    return cast(float, entity.data) / 1000


def _get_charge_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the charging_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    charging_status = data.get_charging_status() if data else None
    return charging_status.name.lower() if charging_status else None


def _get_plug_state_formatted(entity: RenaultSensor[T]) -> str | None:
    """Return the plug_status of this entity."""
    data = cast(KamereonVehicleBatteryStatusData, entity.coordinator.data)
    plug_status = data.get_plug_status() if data else None
    return plug_status.name.lower() if plug_status else None


def _get_rounded_value(entity: RenaultSensor[T]) -> float:
    """Return the rounded value of this entity."""
    return round(cast(float, entity.data))


def _get_utc_value(entity: RenaultSensor[T]) -> datetime:
    """Return the UTC value of this entity."""
    original_dt = parse_datetime(cast(str, entity.data))
    if TYPE_CHECKING:
        assert original_dt is not None
    return as_utc(original_dt)


SENSOR_TYPES: tuple[RenaultSensorEntityDescription[Any], ...] = (
    RenaultSensorEntityDescription(
        key="battery_level",
        coordinator="battery",
        data_key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RenaultSensorEntityDescription(
        key="charge_state",
        coordinator="battery",
        data_key="chargingStatus",
        translation_key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
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
    RenaultSensorEntityDescription(
        key="charging_remaining_time",
        coordinator="battery",
        data_key="chargingRemainingTime",
        device_class=SensorDeviceClass.DURATION,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="charging_remaining_time",
    ),
    RenaultSensorEntityDescription(
        # For vehicles that DO NOT report charging power in watts, this seems to
        # correspond to the maximum power that would be admissible by the car based
        # on the battery state, regardless of the type of charger.
        key="charging_power",
        condition_lambda=lambda a: not a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="admissible_charging_power",
    ),
    RenaultSensorEntityDescription(
        # For vehicles that DO report charging power in watts, this is the power
        # effectively being transferred to the car.
        key="charging_power",
        condition_lambda=lambda a: a.details.reports_charging_power_in_watts(),
        coordinator="battery",
        data_key="chargingInstantaneousPower",
        device_class=SensorDeviceClass.POWER,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_lambda=_get_charging_power,
        translation_key="charging_power",
    ),
    RenaultSensorEntityDescription(
        key="plug_state",
        coordinator="battery",
        data_key="plugStatus",
        translation_key="plug_state",
        device_class=SensorDeviceClass.ENUM,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        options=[
            "unplugged",
            "plugged",
            "plugged_waiting_for_charge",
            "plug_error",
            "plug_unknown",
        ],
        value_lambda=_get_plug_state_formatted,
    ),
    RenaultSensorEntityDescription(
        key="battery_autonomy",
        coordinator="battery",
        data_key="batteryAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_autonomy",
    ),
    RenaultSensorEntityDescription(
        key="battery_available_energy",
        coordinator="battery",
        data_key="batteryAvailableEnergy",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        translation_key="battery_available_energy",
    ),
    RenaultSensorEntityDescription(
        key="battery_temperature",
        coordinator="battery",
        data_key="batteryTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_temperature",
    ),
    RenaultSensorEntityDescription(
        key="battery_last_activity",
        coordinator="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="timestamp",
        entity_class=RenaultSensor[KamereonVehicleBatteryStatusData],
        entity_registry_enabled_default=False,
        value_lambda=_get_utc_value,
        translation_key="battery_last_activity",
    ),
    RenaultSensorEntityDescription(
        key="mileage",
        coordinator="cockpit",
        data_key="totalMileage",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_lambda=_get_rounded_value,
        translation_key="mileage",
    ),
    RenaultSensorEntityDescription(
        key="fuel_autonomy",
        coordinator="cockpit",
        data_key="fuelAutonomy",
        device_class=SensorDeviceClass.DISTANCE,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
        translation_key="fuel_autonomy",
    ),
    RenaultSensorEntityDescription(
        key="fuel_quantity",
        coordinator="cockpit",
        data_key="fuelQuantity",
        device_class=SensorDeviceClass.VOLUME,
        entity_class=RenaultSensor[KamereonVehicleCockpitData],
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        requires_fuel=True,
        value_lambda=_get_rounded_value,
        translation_key="fuel_quantity",
    ),
    RenaultSensorEntityDescription(
        key="outside_temperature",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TEMPERATURE,
        data_key="externalTemperature",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outside_temperature",
    ),
    RenaultSensorEntityDescription(
        key="hvac_soc_threshold",
        coordinator="hvac_status",
        data_key="socThreshold",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        native_unit_of_measurement=PERCENTAGE,
        translation_key="hvac_soc_threshold",
    ),
    RenaultSensorEntityDescription(
        key="hvac_last_activity",
        coordinator="hvac_status",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleHvacStatusData],
        entity_registry_enabled_default=False,
        translation_key="hvac_last_activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="location_last_activity",
        coordinator="location",
        device_class=SensorDeviceClass.TIMESTAMP,
        data_key="lastUpdateTime",
        entity_class=RenaultSensor[KamereonVehicleLocationData],
        entity_registry_enabled_default=False,
        translation_key="location_last_activity",
        value_lambda=_get_utc_value,
    ),
    RenaultSensorEntityDescription(
        key="res_state",
        coordinator="res_state",
        data_key="details",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        translation_key="res_state",
    ),
    RenaultSensorEntityDescription(
        key="res_state_code",
        coordinator="res_state",
        data_key="code",
        entity_class=RenaultSensor[KamereonVehicleResStateData],
        entity_registry_enabled_default=False,
        translation_key="res_state_code",
    ),
)
