"""Volvo sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, cast

from volvocarsapi.models import (
    VolvoCarsApiBaseModel,
    VolvoCarsValue,
    VolvoCarsValueField,
    VolvoCarsValueStatusField,
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
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_BATTERY_CAPACITY
from .coordinator import VolvoBaseCoordinator, VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription, value_to_translation_key

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VolvoSensorDescription(VolvoEntityDescription, SensorEntityDescription):
    """Describes a Volvo sensor entity."""

    source_fields: list[str] | None = None
    value_fn: Callable[[VolvoCarsValue], Any] | None = None


def _availability_status(field: VolvoCarsValue) -> str:
    reason = field.get("unavailable_reason")
    return reason if reason else str(field.value)


def _calculate_time_to_service(field: VolvoCarsValue) -> int:
    value = int(field.value)

    # Always express value in days
    if isinstance(field, VolvoCarsValueField) and field.unit == "months":
        return value * 30

    return value


def _charging_power_value(field: VolvoCarsValue) -> int:
    return (
        int(field.value)
        if isinstance(field, VolvoCarsValueStatusField) and field.status == "OK"
        else 0
    )


def _to_capitalize(field: VolvoCarsValue) -> str:
    return cast(str, field.value).replace("_", " ").lower().capitalize()


_DESCRIPTIONS: tuple[VolvoSensorDescription, ...] = (
    # command-accessibility endpoint
    VolvoSensorDescription(
        key="availability",
        api_field="availabilityStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "car_in_use",
            "no_internet",
            "ota_installation_in_progress",
            "power_saving_mode",
        ],
        value_fn=_availability_status,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption",
        api_field="averageEnergyConsumption",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_automatic",
        api_field="averageEnergyConsumptionAutomatic",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_charge",
        api_field="averageEnergyConsumptionSinceCharge",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption",
        api_field="averageFuelConsumption",
        native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption_automatic",
        api_field="averageFuelConsumptionAutomatic",
        native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed",
        api_field="averageSpeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed_automatic",
        api_field="averageSpeedAutomatic",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # vehicle endpoint
    VolvoSensorDescription(
        key="battery_capacity",
        api_field=DATA_BATTERY_CAPACITY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # fuel & energy state endpoint
    VolvoSensorDescription(
        key="battery_charge_level",
        api_field="batteryChargeLevel",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charger_connection_status",
        api_field="chargerConnectionStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "connected",
            "disconnected",
            "fault",
        ],
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charging_current_limit",
        api_field="chargingCurrentLimit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charging_power",
        api_field="chargingPower",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_charging_power_value,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charging_power_status",
        api_field="chargerPowerStatus",
        value_fn=_to_capitalize,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charging_status",
        api_field="chargingStatus",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "charging",
            "discharging",
            "done",
            "error",
            "idle",
            "scheduled",
        ],
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="charging_type",
        api_field="chargingType",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "ac",
            "dc",
            "none",
        ],
    ),
    # statistics & energy state endpoint
    VolvoSensorDescription(
        key="distance_to_empty_battery",
        api_field="",
        source_fields=["distanceToEmptyBattery", "electricRange"],
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="distance_to_empty_tank",
        api_field="distanceToEmptyTank",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="distance_to_service",
        api_field="distanceToService",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="engine_time_to_service",
        api_field="engineHoursToService",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="estimated_charging_time",
        api_field="estimatedChargingTimeToTargetBatteryChargeLevel",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # fuel endpoint
    VolvoSensorDescription(
        key="fuel_amount",
        api_field="fuelAmount",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # odometer endpoint
    VolvoSensorDescription(
        key="odometer",
        api_field="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="target_battery_charge_level",
        api_field="targetBatteryChargeLevel",
        native_unit_of_measurement=PERCENTAGE,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="time_to_service",
        api_field="timeToService",
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_calculate_time_to_service,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="trip_meter_automatic",
        api_field="tripMeterAutomatic",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="trip_meter_manual",
        api_field="tripMeterManual",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    entities: list[VolvoSensor] = []
    added_keys: set[str] = set()

    def _add_entity(
        coordinator: VolvoBaseCoordinator, description: VolvoSensorDescription
    ) -> None:
        entities.append(VolvoSensor(coordinator, description))
        added_keys.add(description.key)

    coordinators = entry.runtime_data

    for coordinator in coordinators:
        for description in _DESCRIPTIONS:
            if description.key in added_keys:
                continue

            if description.source_fields:
                for field in description.source_fields:
                    if field in coordinator.data:
                        description = replace(description, api_field=field)
                        _add_entity(coordinator, description)
            elif description.api_field in coordinator.data:
                _add_entity(coordinator, description)

    async_add_entities(entities)


class VolvoSensor(VolvoEntity, SensorEntity):
    """Volvo sensor."""

    entity_description: VolvoSensorDescription

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        if api_field is None:
            self._attr_native_value = None
            return

        assert isinstance(api_field, VolvoCarsValue)

        native_value = (
            api_field.value
            if self.entity_description.value_fn is None
            else self.entity_description.value_fn(api_field)
        )

        if self.device_class == SensorDeviceClass.ENUM:
            # Entities having an "unknown" value should report None as the state
            native_value = str(native_value)
            native_value = (
                value_to_translation_key(native_value)
                if native_value.upper() != "UNSPECIFIED"
                else None
            )

        self._attr_native_value = native_value
