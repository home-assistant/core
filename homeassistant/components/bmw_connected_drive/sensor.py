"""Support for reading vehicle status from MyBMW portal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

from bimmer_connected.models import ValueWithUnit
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LENGTH, PERCENTAGE, VOLUME, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BMWBaseEntity
from .const import CLIMATE_ACTIVITY_STATE, DOMAIN, UNIT_MAP
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    key_class: str | None = None
    unit_type: str | None = None
    value: Callable = lambda x, y: x
    is_available: Callable[[MyBMWVehicle], bool] = lambda v: v.is_lsc_enabled


def convert_and_round(
    state: ValueWithUnit,
    converter: Callable[[float | None, str], float],
    precision: int,
) -> float | None:
    """Safely convert and round a value from ValueWithUnit."""
    if state.value and state.unit:
        return round(
            converter(state.value, UNIT_MAP.get(state.unit, state.unit)), precision
        )
    if state.value:
        return state.value
    return None


SENSOR_TYPES: list[BMWSensorEntityDescription] = [
    # --- Generic ---
    BMWSensorEntityDescription(
        key="ac_current_limit",
        translation_key="ac_current_limit",
        key_class="charging_profile",
        unit_type=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
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
        value=lambda x, y: x.value,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="charging_target",
        translation_key="charging_target",
        key_class="fuel_and_battery",
        unit_type=PERCENTAGE,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_battery_percent",
        translation_key="remaining_battery_percent",
        key_class="fuel_and_battery",
        unit_type=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    # --- Specific ---
    BMWSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        unit_type=LENGTH,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BMWSensorEntityDescription(
        key="remaining_range_total",
        translation_key="remaining_range_total",
        key_class="fuel_and_battery",
        unit_type=LENGTH,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BMWSensorEntityDescription(
        key="remaining_range_electric",
        translation_key="remaining_range_electric",
        key_class="fuel_and_battery",
        unit_type=LENGTH,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
        state_class=SensorStateClass.MEASUREMENT,
        is_available=lambda v: v.is_lsc_enabled and v.has_electric_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_range_fuel",
        translation_key="remaining_range_fuel",
        key_class="fuel_and_battery",
        unit_type=LENGTH,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
        state_class=SensorStateClass.MEASUREMENT,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_fuel",
        translation_key="remaining_fuel",
        key_class="fuel_and_battery",
        unit_type=VOLUME,
        value=lambda x, hass: convert_and_round(x, hass.config.units.volume, 2),
        state_class=SensorStateClass.MEASUREMENT,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="remaining_fuel_percent",
        translation_key="remaining_fuel_percent",
        key_class="fuel_and_battery",
        unit_type=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        is_available=lambda v: v.is_lsc_enabled and v.has_combustion_drivetrain,
    ),
    BMWSensorEntityDescription(
        key="activity",
        translation_key="climate_status",
        key_class="climate",
        device_class=SensorDeviceClass.ENUM,
        options=CLIMATE_ACTIVITY_STATE,
        value=lambda x, _: x.lower() if x != "UNKNOWN" else None,
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

        # Set the correct unit of measurement based on the unit_type
        if description.unit_type:
            self._attr_native_unit_of_measurement = (
                coordinator.hass.config.units.as_dict().get(description.unit_type)
                or description.unit_type
            )

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
        self._attr_native_value = cast(
            StateType, self.entity_description.value(state, self.hass)
        )
        super()._handle_coordinator_update()
