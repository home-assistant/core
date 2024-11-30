"""Support for reading vehicle status from MyBMW portal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging

from bimmer_connected.models import StrEnum, ValueWithUnit
from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.climate import ClimateActivityState
from bimmer_connected.vehicle.fuel_and_battery import ChargingState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfLength,
    UnitOfPressure,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BMWConfigEntry
from .coordinator import BMWDataUpdateCoordinator
from .entity import BMWBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    key_class: str | None = None
    is_available: Callable[[MyBMWVehicle], bool] = lambda v: v.is_lsc_enabled


TIRES = ["front_left", "front_right", "rear_left", "rear_right"]

SENSOR_TYPES: list[BMWSensorEntityDescription] = [
    BMWSensorEntityDescription(
        key="charging_profile.ac_current_limit",
        translation_key="ac_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.charging_start_time",
        translation_key="charging_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.charging_end_time",
        translation_key="charging_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value.lower() for s in ChargingState if s != ChargingState.UNKNOWN],
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.charging_target",
        translation_key="charging_target",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_battery_percent",
        translation_key="remaining_battery_percent",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_range_total",
        translation_key="remaining_range_total",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_range_electric",
        translation_key="remaining_range_electric",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_range_fuel",
        translation_key="remaining_range_fuel",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_fuel",
        translation_key="remaining_fuel",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="fuel_and_battery.remaining_fuel_percent",
        translation_key="remaining_fuel_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="climate.activity",
        translation_key="climate_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            s.value.lower()
            for s in ClimateActivityState
            if s != ClimateActivityState.UNKNOWN
        ],
        is_available=lambda v: v.is_remote_climate_stop_enabled,
    ),
    *[
        BMWSensorEntityDescription(
            key=f"tires.{tire}.current_pressure",
            translation_key=f"{tire}_current_pressure",
            device_class=SensorDeviceClass.PRESSURE,
            native_unit_of_measurement=UnitOfPressure.KPA,
            suggested_unit_of_measurement=UnitOfPressure.BAR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            is_available=lambda v: v.is_lsc_enabled and v.tires is not None,
        )
        for tire in TIRES
    ],
    *[
        BMWSensorEntityDescription(
            key=f"tires.{tire}.target_pressure",
            translation_key=f"{tire}_target_pressure",
            device_class=SensorDeviceClass.PRESSURE,
            native_unit_of_measurement=UnitOfPressure.KPA,
            suggested_unit_of_measurement=UnitOfPressure.BAR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            is_available=lambda v: v.is_lsc_enabled and v.tires is not None,
        )
        for tire in TIRES
    ],
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMWConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW sensors from config entry."""
    coordinator = config_entry.runtime_data.coordinator

    entities = [
        BMWSensor(coordinator, vehicle, description)
        for vehicle in coordinator.account.vehicles
        for description in SENSOR_TYPES
        if description.is_available(vehicle)
    ]

    async_add_entities(entities)


class BMWSensor(BMWBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    entity_description: BMWSensorEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWSensorEntityDescription,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Updating sensor '%s' of %s", self.entity_description.key, self.vehicle.name
        )

        key_path = self.entity_description.key.split(".")
        state = getattr(self.vehicle, key_path.pop(0))

        for key in key_path:
            state = getattr(state, key)

        # For datetime without tzinfo, we assume it to be the same timezone as the HA instance
        if isinstance(state, datetime.datetime) and state.tzinfo is None:
            state = state.replace(tzinfo=dt_util.get_default_time_zone())
        # For enum types, we only want the value
        elif isinstance(state, ValueWithUnit):
            state = state.value
        # Get lowercase values from StrEnum
        elif isinstance(state, StrEnum):
            state = state.value.lower()
            if state == STATE_UNKNOWN:
                state = None

        self._attr_native_value = state
        super()._handle_coordinator_update()
