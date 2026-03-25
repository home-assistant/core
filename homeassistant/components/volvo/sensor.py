"""Volvo sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

from volvocarsapi.models import (
    VolvoCarsApiBaseModel,
    VolvoCarsLocation,
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
    DEGREE,
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
from homeassistant.helpers.typing import StateType

from .const import API_NONE_VALUE, DATA_BATTERY_CAPACITY
from .coordinator import VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription, value_to_translation_key

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VolvoSensorDescription(VolvoEntityDescription, SensorEntityDescription):
    """Describes a Volvo sensor entity."""

    value_fn: Callable[[VolvoCarsApiBaseModel], StateType] | None = None


def _availability_status(field: VolvoCarsApiBaseModel) -> str:
    reason = field.get("unavailable_reason")

    if reason:
        return str(reason)

    if isinstance(field, VolvoCarsValue):
        return str(field.value)

    return ""


def _calculate_time_to_service(field: VolvoCarsApiBaseModel) -> int:
    if not isinstance(field, VolvoCarsValueField):
        return 0

    value = int(field.value)
    # Always express value in days
    return value * 30 if field.unit == "months" else value


def _charging_power_value(field: VolvoCarsApiBaseModel) -> int:
    return (
        field.value
        if isinstance(field, VolvoCarsValueStatusField) and isinstance(field.value, int)
        else 0
    )


def _charging_power_status_value(field: VolvoCarsApiBaseModel) -> str | None:
    status = cast(str, field.value) if isinstance(field, VolvoCarsValue) else ""

    if status.lower() in _CHARGING_POWER_STATUS_OPTIONS:
        return status

    _LOGGER.warning(
        "Unknown value '%s' for charging_power_status. Please report it at https://github.com/home-assistant/core/issues/new?template=bug_report.yml",
        status,
    )
    return None


def _direction_value(field: VolvoCarsApiBaseModel) -> str | None:
    return field.properties.heading if isinstance(field, VolvoCarsLocation) else None


_CHARGING_POWER_STATUS_OPTIONS = [
    "fault",
    "power_available_but_not_activated",
    "providing_power",
    "no_power_available",
]

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
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption",
        api_field="averageEnergyConsumption",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_automatic",
        api_field="averageEnergyConsumptionAutomatic",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_energy_consumption_charge",
        api_field="averageEnergyConsumptionSinceCharge",
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption",
        api_field="averageFuelConsumption",
        native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_fuel_consumption_automatic",
        api_field="averageFuelConsumptionAutomatic",
        native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed",
        api_field="averageSpeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="average_speed_automatic",
        api_field="averageSpeedAutomatic",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
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
        suggested_display_precision=0,
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
        device_class=SensorDeviceClass.ENUM,
        options=_CHARGING_POWER_STATUS_OPTIONS,
        value_fn=_charging_power_status_value,
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
    # location endpoint
    VolvoSensorDescription(
        key="direction",
        api_field="location",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=_direction_value,
    ),
    # statistics endpoint
    # We're not using `electricRange` from the energy state endpoint because
    # the official app seems to use `distanceToEmptyBattery`.
    # In issue #150213, a user described the behavior as follows:
    # - For a `distanceToEmptyBattery` of 250km, the `electricRange` was 150mi
    # - For a `distanceToEmptyBattery` of 260km, the `electricRange` was 160mi
    VolvoSensorDescription(
        key="distance_to_empty_battery",
        api_field="distanceToEmptyBattery",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="distance_to_empty_tank",
        api_field="distanceToEmptyTank",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="distance_to_service",
        api_field="distanceToService",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
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
        suggested_display_precision=1,
    ),
    # odometer endpoint
    VolvoSensorDescription(
        key="odometer",
        api_field="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    # diagnostics endpoint
    VolvoSensorDescription(
        key="service_warning",
        api_field="serviceWarning",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "distance_driven_almost_time_for_service",
            "distance_driven_overdue_for_service",
            "distance_driven_time_for_service",
            "engine_hours_almost_time_for_service",
            "engine_hours_overdue_for_service",
            "engine_hours_time_for_service",
            "no_warning",
            "regular_maintenance_almost_time_for_service",
            "regular_maintenance_overdue_for_service",
            "regular_maintenance_time_for_service",
            "unknown_warning",
        ],
    ),
    # energy state endpoint
    VolvoSensorDescription(
        key="target_battery_charge_level",
        api_field="targetBatteryChargeLevel",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
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
        suggested_display_precision=0,
    ),
    # statistics endpoint
    VolvoSensorDescription(
        key="trip_meter_manual",
        api_field="tripMeterManual",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""

    entities: dict[str, VolvoSensor] = {}
    coordinators = entry.runtime_data.interval_coordinators

    for coordinator in coordinators:
        for description in _DESCRIPTIONS:
            if description.key in entities:
                continue

            if description.api_field in coordinator.data:
                entities[description.key] = VolvoSensor(coordinator, description)

    async_add_entities(entities.values())


class VolvoSensor(VolvoEntity, SensorEntity):
    """Volvo sensor."""

    entity_description: VolvoSensorDescription

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        if api_field is None:
            self._attr_native_value = None
            return

        native_value = None

        if self.entity_description.value_fn:
            native_value = self.entity_description.value_fn(api_field)
        elif isinstance(api_field, VolvoCarsValue):
            native_value = api_field.value

        if self.device_class == SensorDeviceClass.ENUM and native_value:
            # Entities having an "unknown" value should report None as the state
            native_value = str(native_value)
            native_value = (
                value_to_translation_key(native_value)
                if native_value.upper() != API_NONE_VALUE
                else None
            )

        self._attr_native_value = native_value
