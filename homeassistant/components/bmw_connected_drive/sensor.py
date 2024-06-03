"""Support for reading vehicle status from MyBMW portal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging

from bimmer_connected.models import StrEnum, ValueWithUnit
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfLength,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BMWBaseEntity
from .const import CLIMATE_ACTIVITY_STATE, DOMAIN
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    key_class: str | None = None
    is_available: Callable[[MyBMWVehicle], bool] = lambda v: v.is_lsc_enabled


SENSOR_TYPES: list[BMWSensorEntityDescription] = [
    BMWSensorEntityDescription(
        key="ac_current_limit",
        translation_key="ac_current_limit",
        key_class="charging_profile",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="charging_start_time",
        translation_key="charging_start_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="charging_end_time",
        translation_key="charging_end_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        key_class="fuel_and_battery",
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="charging_target",
        translation_key="charging_target",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_battery_percent",
        translation_key="remaining_battery_percent",
        key_class="fuel_and_battery",
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
        key="remaining_range_total",
        translation_key="remaining_range_total",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    BMWSensorEntityDescription(
        key="remaining_range_electric",
        translation_key="remaining_range_electric",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_range_fuel",
        translation_key="remaining_range_fuel",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_fuel",
        translation_key="remaining_fuel",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_fuel_percent",
        translation_key="remaining_fuel_percent",
        key_class="fuel_and_battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="activity",
        translation_key="climate_status",
        key_class="climate",
        device_class=SensorDeviceClass.ENUM,
        options=CLIMATE_ACTIVITY_STATE,
        is_available=lambda v: v.is_remote_climate_stop_enabled,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW sensors from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

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
        if self.entity_description.key_class is None:
            state = getattr(self.vehicle, self.entity_description.key)
        else:
            state = getattr(
                getattr(self.vehicle, self.entity_description.key_class),
                self.entity_description.key,
            )

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

            # special handling for charging_status to avoid a breaking change
            if self.entity_description.key == "charging_status" and state:
                state = state.upper()

        self._attr_native_value = state
        super()._handle_coordinator_update()
