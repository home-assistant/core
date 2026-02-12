"""Sensor platform for Miele integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final, cast

from pymiele import MieleDevice, MieleFillingLevel, MieleTemperature

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    COFFEE_SYSTEM_PROFILE,
    DISABLED_TEMP_ENTITIES,
    DOMAIN,
    PROGRAM_IDS,
    PROGRAM_PHASE,
    MieleAppliance,
    PlatePowerStep,
    StateDryingStep,
    StateProgramType,
    StateStatus,
)
from .coordinator import (
    MieleAuxDataUpdateCoordinator,
    MieleConfigEntry,
    MieleDataUpdateCoordinator,
)
from .entity import MieleAuxEntity, MieleEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

DEFAULT_PLATE_COUNT = 4

PLATE_COUNT = {
    "KM7575": 6,
    "KM7678": 6,
    "KM7697": 6,
    "KM7699": 5,
    "KM7878": 6,
    "KM7897": 6,
    "KMDA7633": 5,
    "KMDA7634": 5,
    "KMDA7774": 5,
    "KMX": 6,
}

ATTRIBUTE_PROFILE = "profile"


def _get_plate_count(tech_type: str) -> int:
    """Get number of zones for hob."""
    stripped = tech_type.replace(" ", "")
    for prefix, plates in PLATE_COUNT.items():
        if stripped.startswith(prefix):
            return plates
    return DEFAULT_PLATE_COUNT


def _convert_duration(value_list: list[int]) -> int | None:
    """Convert duration to minutes."""
    return value_list[0] * 60 + value_list[1] if value_list else None


def _convert_temperature(
    value_list: list[MieleTemperature], index: int
) -> float | None:
    """Convert temperature object to readable value."""
    if index >= len(value_list):
        return None
    raw_value = cast(int, value_list[index].temperature) / 100.0
    if raw_value in DISABLED_TEMP_ENTITIES:
        return None
    return raw_value


def _get_coffee_profile(value: MieleDevice) -> str | None:
    """Get coffee profile from value."""
    if value.state_program_id is not None:
        for key_range, profile in COFFEE_SYSTEM_PROFILE.items():
            if value.state_program_id in key_range:
                return profile
    return None


def _convert_start_timestamp(
    elapsed_time_list: list[int], start_time_list: list[int]
) -> datetime | None:
    """Convert raw values representing time into start timestamp."""
    now = dt_util.utcnow()
    elapsed_duration = _convert_duration(elapsed_time_list)
    delayed_start_duration = _convert_duration(start_time_list)
    if (elapsed_duration is None or elapsed_duration == 0) and (
        delayed_start_duration is None or delayed_start_duration == 0
    ):
        return None
    if elapsed_duration is not None and elapsed_duration > 0:
        duration = -elapsed_duration
    elif delayed_start_duration is not None and delayed_start_duration > 0:
        duration = delayed_start_duration
    delta = timedelta(minutes=duration)
    return (now + delta).replace(second=0, microsecond=0)


def _convert_finish_timestamp(
    remaining_time_list: list[int], start_time_list: list[int]
) -> datetime | None:
    """Convert raw values representing time into finish timestamp."""
    now = dt_util.utcnow()
    program_duration = _convert_duration(remaining_time_list)
    delayed_start_duration = _convert_duration(start_time_list)
    if program_duration is None or program_duration == 0:
        return None
    duration = program_duration + (
        delayed_start_duration if delayed_start_duration is not None else 0
    )
    delta = timedelta(minutes=duration)
    return (now + delta).replace(second=0, microsecond=0)


@dataclass(frozen=True, kw_only=True)
class MieleSensorDescription[T: (MieleDevice, MieleFillingLevel)](
    SensorEntityDescription
):
    """Class describing Miele sensor entities."""

    value_fn: Callable[[T], StateType | datetime]

    end_value_fn: Callable[[StateType | datetime], StateType | datetime] | None = None
    extra_attributes: dict[str, Callable[[MieleDevice], StateType]] | None = None
    zone: int | None = None
    unique_id_fn: Callable[[str, MieleSensorDescription], str] | None = None


@dataclass
class MieleSensorDefinition[T: (MieleDevice, MieleFillingLevel)]:
    """Class for defining sensor entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleSensorDescription[T]


SENSOR_TYPES: Final[tuple[MieleSensorDefinition[MieleDevice], ...]] = (
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.HOB_HIGHLIGHT,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.HOB_INDUCTION,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.HOB_INDUCT_EXTR,
        ),
        description=MieleSensorDescription(
            key="state_status",
            translation_key="status",
            value_fn=lambda value: value.state_status,
            device_class=SensorDeviceClass.ENUM,
            options=sorted(set(StateStatus.keys())),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_program_id",
            translation_key="program_id",
            device_class=SensorDeviceClass.ENUM,
            value_fn=lambda value: value.state_program_id,
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.COFFEE_SYSTEM,),
        description=MieleSensorDescription(
            key="state_program_id",
            translation_key="program_id",
            device_class=SensorDeviceClass.ENUM,
            value_fn=lambda value: value.state_program_id,
            extra_attributes={
                ATTRIBUTE_PROFILE: _get_coffee_profile,
            },
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_program_phase",
            translation_key="program_phase",
            value_fn=lambda value: value.state_program_phase,
            device_class=SensorDeviceClass.ENUM,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_program_type",
            translation_key="program_type",
            value_fn=lambda value: StateProgramType(value.state_program_type).name,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
            options=sorted(set(StateProgramType.keys())),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleSensorDescription(
            key="current_energy_consumption",
            translation_key="energy_consumption",
            value_fn=lambda value: value.current_energy_consumption,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=1,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleSensorDescription(
            key="energy_forecast",
            translation_key="energy_forecast",
            value_fn=(
                lambda value: (
                    value.energy_forecast * 100
                    if value.energy_forecast is not None
                    else None
                )
            ),
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.DISHWASHER,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleSensorDescription(
            key="current_water_consumption",
            translation_key="water_consumption",
            value_fn=lambda value: value.current_water_consumption,
            device_class=SensorDeviceClass.WATER,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.DISHWASHER,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleSensorDescription(
            key="water_forecast",
            translation_key="water_forecast",
            value_fn=(
                lambda value: (
                    value.water_forecast * 100
                    if value.water_forecast is not None
                    else None
                )
            ),
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.WASHER_DRYER,
        ),
        description=MieleSensorDescription(
            key="state_spinning_speed",
            translation_key="spin_speed",
            value_fn=lambda value: value.state_spinning_speed,
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_remaining_time",
            translation_key="remaining_time",
            value_fn=lambda value: _convert_duration(value.state_remaining_time),
            end_value_fn=lambda last_value: 0,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_elapsed_time",
            translation_key="elapsed_time",
            value_fn=lambda value: _convert_duration(value.state_elapsed_time),
            end_value_fn=lambda last_value: last_value,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_start_time",
            translation_key="start_time",
            value_fn=lambda value: _convert_duration(value.state_start_time),
            end_value_fn=lambda last_value: None,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfTime.HOURS,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_finish_timestamp",
            translation_key="finish",
            value_fn=lambda value: _convert_finish_timestamp(
                value.state_remaining_time, value.state_start_time
            ),
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_start_timestamp",
            translation_key="start",
            value_fn=lambda value: _convert_start_timestamp(
                value.state_elapsed_time, value.state_start_time
            ),
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_temperature_1",
            zone=1,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(value.state_temperatures, 0),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleSensorDescription(
            key="state_temperature_2",
            zone=2,
            device_class=SensorDeviceClass.TEMPERATURE,
            translation_key="temperature_zone_2",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(value.state_temperatures, 1),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleSensorDescription(
            key="state_temperature_3",
            zone=3,
            device_class=SensorDeviceClass.TEMPERATURE,
            translation_key="temperature_zone_3",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(value.state_temperatures, 2),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_core_target_temperature",
            translation_key="core_target_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(
                value.state_core_target_temperature, 0
            ),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_target_temperature",
            translation_key="target_temperature",
            zone=1,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(
                value.state_target_temperature, 0
            ),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN_COMBI,
        ),
        description=MieleSensorDescription(
            key="state_core_temperature",
            translation_key="core_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: _convert_temperature(
                value.state_core_temperature, 0
            ),
        ),
    ),
    *(
        MieleSensorDefinition(
            types=(
                MieleAppliance.HOB_HIGHLIGHT,
                MieleAppliance.HOB_INDUCT_EXTR,
                MieleAppliance.HOB_INDUCTION,
            ),
            description=MieleSensorDescription(
                key="state_plate_step",
                translation_key="plate",
                translation_placeholders={"plate_no": str(i)},
                zone=i,
                device_class=SensorDeviceClass.ENUM,
                options=sorted(PlatePowerStep.keys()),
                value_fn=lambda value: None,
                unique_id_fn=lambda device_id, description: (
                    f"{device_id}-{description.key}-{description.zone}"
                ),
            ),
        )
        for i in range(1, 7)
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
        ),
        description=MieleSensorDescription(
            key="state_drying_step",
            translation_key="drying_step",
            value_fn=lambda value: (
                StateDryingStep(cast(int, value.state_drying_step)).name
            ),
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
            options=sorted(StateDryingStep.keys()),
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.ROBOT_VACUUM_CLEANER,),
        description=MieleSensorDescription(
            key="state_battery",
            value_fn=lambda value: value.state_battery_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.BATTERY,
        ),
    ),
)

POLLED_SENSOR_TYPES: Final[tuple[MieleSensorDefinition[MieleFillingLevel], ...]] = (
    MieleSensorDefinition(
        types=(MieleAppliance.WASHING_MACHINE,),
        description=MieleSensorDescription[MieleFillingLevel](
            key="twin_dos_1_level",
            translation_key="twin_dos_1_level",
            value_fn=lambda value: value.twin_dos_container_1_filling_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.WASHING_MACHINE,),
        description=MieleSensorDescription[MieleFillingLevel](
            key="twin_dos_2_level",
            translation_key="twin_dos_2_level",
            value_fn=lambda value: value.twin_dos_container_2_filling_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.DISHWASHER,),
        description=MieleSensorDescription[MieleFillingLevel](
            key="power_disk_level",
            translation_key="power_disk_level",
            value_fn=lambda value: value.power_disc_filling_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.DISHWASHER,),
        description=MieleSensorDescription[MieleFillingLevel](
            key="salt_level",
            translation_key="salt_level",
            value_fn=lambda value: value.salt_filling_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleSensorDefinition(
        types=(MieleAppliance.DISHWASHER,),
        description=MieleSensorDescription[MieleFillingLevel](
            key="rinse_aid_level",
            translation_key="rinse_aid_level",
            value_fn=lambda value: value.rinse_aid_filling_level,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    aux_coordinator = config_entry.runtime_data.aux_coordinator
    added_devices: set[str] = set()  # device_id
    added_entities: set[str] = set()  # unique_id

    def _get_entity_class(
        definition: MieleSensorDefinition[MieleDevice],
    ) -> type[MieleSensor]:
        """Get the entity class for the sensor."""
        return {
            "state_status": MieleStatusSensor,
            "state_program_id": MieleProgramIdSensor,
            "state_program_phase": MielePhaseSensor,
            "state_plate_step": MielePlateSensor,
            "state_elapsed_time": MieleTimeSensor,
            "state_remaining_time": MieleTimeSensor,
            "state_start_time": MieleTimeSensor,
            "state_start_timestamp": MieleAbsoluteTimeSensor,
            "state_finish_timestamp": MieleAbsoluteTimeSensor,
            "current_energy_consumption": MieleConsumptionSensor,
            "current_water_consumption": MieleConsumptionSensor,
        }.get(definition.description.key, MieleSensor)

    def _is_entity_registered(unique_id: str) -> bool:
        """Check if the entity is already registered."""
        entity_registry = er.async_get(hass)
        return any(
            entry.platform == DOMAIN and entry.unique_id == unique_id
            for entry in entity_registry.entities.values()
        )

    def _is_sensor_enabled(
        definition: MieleSensorDefinition[MieleDevice],
        device: MieleDevice,
        unique_id: str,
    ) -> bool:
        """Check if the sensor is enabled."""
        if (
            definition.description.device_class == SensorDeviceClass.TEMPERATURE
            and definition.description.value_fn(device) is None
            and definition.description.zone != 1
        ):
            # all appliances supporting temperature have at least zone 1, for other zones
            # don't create entity if API signals that datapoint is disabled, unless the sensor
            # already appeared in the past (= it provided a valid value)
            return _is_entity_registered(unique_id)
        if (
            definition.description.key == "state_plate_step"
            and definition.description.zone is not None
            and definition.description.zone > _get_plate_count(device.tech_type)
        ):
            # don't create plate entity if not expected by the appliance tech type
            return False
        return True

    def _enabled_aux_sensor(
        definition: MieleSensorDefinition[MieleFillingLevel], level: MieleFillingLevel
    ) -> bool:
        """Check if aux sensors are enabled."""
        return not (
            definition.description.value_fn is not None
            and definition.description.value_fn(level) is None
        )

    def _async_add_devices() -> None:
        nonlocal added_devices, added_entities
        entities: list = []
        entity_class: type[MieleSensor]
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        for device_id, device in coordinator.data.devices.items():
            for definition in SENSOR_TYPES:
                # device is not supported, skip
                if device.device_type not in definition.types:
                    continue

                entity_class = _get_entity_class(definition)
                unique_id = (
                    definition.description.unique_id_fn(
                        device_id, definition.description
                    )
                    if definition.description.unique_id_fn is not None
                    else MieleEntity.get_unique_id(device_id, definition.description)
                )

                # entity was already added, skip
                if device_id not in new_devices_set and unique_id in added_entities:
                    continue

                # sensors is not enabled, skip
                if not _is_sensor_enabled(
                    definition,
                    device,
                    unique_id,
                ):
                    continue

                added_entities.add(unique_id)
                entities.append(
                    entity_class(coordinator, device_id, definition.description)
                )
        async_add_entities(entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_devices))
    _async_add_devices()

    async_add_entities(
        MieleAuxSensor(aux_coordinator, device_id, definition.description)
        for device_id in aux_coordinator.data.filling_levels
        for definition in POLLED_SENSOR_TYPES
        if _enabled_aux_sensor(
            definition, aux_coordinator.data.filling_levels[device_id]
        )
    )


APPLIANCE_ICONS = {
    MieleAppliance.WASHING_MACHINE: "mdi:washing-machine",
    MieleAppliance.TUMBLE_DRYER: "mdi:tumble-dryer",
    MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL: "mdi:tumble-dryer",
    MieleAppliance.DISHWASHER: "mdi:dishwasher",
    MieleAppliance.OVEN: "mdi:chef-hat",
    MieleAppliance.OVEN_MICROWAVE: "mdi:chef-hat",
    MieleAppliance.HOB_HIGHLIGHT: "mdi:pot-steam-outline",
    MieleAppliance.STEAM_OVEN: "mdi:chef-hat",
    MieleAppliance.MICROWAVE: "mdi:microwave",
    MieleAppliance.COFFEE_SYSTEM: "mdi:coffee-maker",
    MieleAppliance.HOOD: "mdi:turbine",
    MieleAppliance.FRIDGE: "mdi:fridge-industrial-outline",
    MieleAppliance.FREEZER: "mdi:fridge-industrial-outline",
    MieleAppliance.FRIDGE_FREEZER: "mdi:fridge-outline",
    MieleAppliance.ROBOT_VACUUM_CLEANER: "mdi:robot-vacuum",
    MieleAppliance.WASHER_DRYER: "mdi:washing-machine",
    MieleAppliance.DISH_WARMER: "mdi:heat-wave",
    MieleAppliance.HOB_INDUCTION: "mdi:pot-steam-outline",
    MieleAppliance.STEAM_OVEN_COMBI: "mdi:chef-hat",
    MieleAppliance.WINE_CABINET: "mdi:glass-wine",
    MieleAppliance.WINE_CONDITIONING_UNIT: "mdi:glass-wine",
    MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT: "mdi:glass-wine",
    MieleAppliance.STEAM_OVEN_MICRO: "mdi:chef-hat",
    MieleAppliance.DIALOG_OVEN: "mdi:chef-hat",
    MieleAppliance.WINE_CABINET_FREEZER: "mdi:glass-wine",
    MieleAppliance.HOB_INDUCT_EXTR: "mdi:pot-steam-outline",
}


class MieleSensor(MieleEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: MieleSensorDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description)
        if description.unique_id_fn is not None:
            self._attr_unique_id = description.unique_id_fn(device_id, description)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra_state_attributes."""
        if self.entity_description.extra_attributes is None:
            return None
        attr = {}
        for key, value in self.entity_description.extra_attributes.items():
            attr[key] = value(self.device)
        return attr


class MieleRestorableSensor(MieleSensor, RestoreSensor):
    """Representation of a Sensor whose internal state can be restored."""

    _attr_native_value: StateType | datetime

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # recover last value from cache when adding entity
        last_data = await self.async_get_last_sensor_data()
        if last_data:
            self._attr_native_value = last_data.native_value  # type: ignore[assignment]

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor.

        It is necessary to override `native_value` to fall back to the default
        attribute-based implementation, instead of the function-based
        implementation in `MieleSensor`.
        """
        return self._attr_native_value

    def _update_native_value(self) -> None:
        """Update the native value attribute of the sensor."""
        self._attr_native_value = self.entity_description.value_fn(self.device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_native_value()
        super()._handle_coordinator_update()


class MieleAuxSensor(MieleAuxEntity, SensorEntity):
    """Representation of a filling level Sensor."""

    entity_description: MieleSensorDescription

    def __init__(
        self,
        coordinator: MieleAuxDataUpdateCoordinator,
        device_id: str,
        description: MieleSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description)
        if description.unique_id_fn is not None:
            self._attr_unique_id = description.unique_id_fn(device_id, description)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the level sensor."""
        return (
            self.entity_description.value_fn(self.levels)
            if self.entity_description.value_fn is not None
            else None
        )


class MielePlateSensor(MieleSensor):
    """Representation of a Sensor."""

    entity_description: MieleSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the plate sensor."""
        # state_plate_step is [] if all zones are off

        return (
            PlatePowerStep(
                cast(
                    int,
                    self.device.state_plate_step[
                        cast(int, self.entity_description.zone) - 1
                    ].value_raw,
                )
            ).name
            if self.device.state_plate_step
            else PlatePowerStep.plate_step_0.name
        )


class MieleStatusSensor(MieleSensor):
    """Representation of the status sensor."""

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description)
        self._attr_name = None
        self._attr_icon = APPLIANCE_ICONS.get(
            MieleAppliance(self.device.device_type),
            "mdi:state-machine",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return StateStatus(self.device.state_status).name

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""
        # This sensor should always be available
        return True


# Some phases have names that are not valid python identifiers, so we need to translate
# them in order to avoid breaking changes
PROGRAM_PHASE_TRANSLATION = {
    "second_espresso": "2nd_espresso",
    "second_grinding": "2nd_grinding",
    "second_pre_brewing": "2nd_pre_brewing",
}


class MielePhaseSensor(MieleSensor):
    """Representation of the program phase sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the phase sensor."""
        program_phase = PROGRAM_PHASE[self.device.device_type](
            self.device.state_program_phase
        ).name

        return (
            PROGRAM_PHASE_TRANSLATION.get(program_phase, program_phase)
            if program_phase is not None
            else None
        )

    @property
    def options(self) -> list[str]:
        """Return the options list for the actual device type."""
        phases = PROGRAM_PHASE[self.device.device_type].keys()
        return sorted([PROGRAM_PHASE_TRANSLATION.get(phase, phase) for phase in phases])


class MieleProgramIdSensor(MieleSensor):
    """Representation of the program id sensor."""

    _unrecorded_attributes = frozenset({ATTRIBUTE_PROFILE})

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return (
            PROGRAM_IDS[self.device.device_type](self.device.state_program_id).name
            if self.device.device_type in PROGRAM_IDS
            else None
        )

    @property
    def options(self) -> list[str]:
        """Return the options list for the actual device type."""
        return sorted(PROGRAM_IDS.get(self.device.device_type, {}).keys())


class MieleTimeSensor(MieleRestorableSensor):
    """Representation of time sensors keeping state from cache."""

    def _update_native_value(self) -> None:
        """Update the last value of the sensor."""

        current_value = self.entity_description.value_fn(self.device)
        current_status = StateStatus(self.device.state_status).name

        # report end-specific value when program ends (some devices are immediately reporting 0...)
        if (
            current_status == StateStatus.program_ended.name
            and self.entity_description.end_value_fn is not None
        ):
            self._attr_native_value = self.entity_description.end_value_fn(
                self._attr_native_value
            )

        # keep value when program ends if no function is specified
        elif current_status == StateStatus.program_ended.name:
            pass

        # force unknown when appliance is not working (some devices are keeping last value until a new cycle starts)
        elif current_status in (
            StateStatus.off.name,
            StateStatus.on.name,
            StateStatus.idle.name,
        ):
            self._attr_native_value = None

        # otherwise, cache value and return it
        else:
            self._attr_native_value = current_value


class MieleAbsoluteTimeSensor(MieleRestorableSensor):
    """Representation of absolute time sensors handling precision correctness."""

    _previous_value: StateType | datetime = None

    def _update_native_value(self) -> None:
        """Update the last value of the sensor."""
        current_value = self.entity_description.value_fn(self.device)
        current_status = StateStatus(self.device.state_status).name

        # The API reports with minute precision, to avoid changing
        # the value too often, we keep the cached value if it differs
        # less than 90s from the new value
        if (
            isinstance(self._previous_value, datetime)
            and isinstance(current_value, datetime)
            and (
                self._previous_value - timedelta(seconds=90)
                < current_value
                < self._previous_value + timedelta(seconds=90)
            )
        ) or current_status == StateStatus.program_ended.name:
            return

        # force unknown when appliance is not working (some devices are keeping last value until a new cycle starts)
        if current_status in (
            StateStatus.off.name,
            StateStatus.on.name,
            StateStatus.idle.name,
        ):
            self._attr_native_value = None

        # otherwise, cache value and return it
        else:
            self._attr_native_value = current_value
            self._previous_value = current_value


class MieleConsumptionSensor(MieleRestorableSensor):
    """Representation of consumption sensors keeping state from cache."""

    _is_reporting: bool = False

    def _update_native_value(self) -> None:
        """Update the last value of the sensor."""
        current_value = self.entity_description.value_fn(self.device)
        current_status = StateStatus(self.device.state_status).name
        # Guard for corrupt restored value
        restored_value = (
            self._attr_native_value
            if isinstance(self._attr_native_value, (int, float))
            else 0
        )
        last_value = (
            float(cast(str, restored_value))
            if self._attr_native_value is not None
            else 0
        )

        # Force unknown when appliance is not able to report consumption
        if current_status in (
            StateStatus.on.name,
            StateStatus.off.name,
            StateStatus.programmed.name,
            StateStatus.waiting_to_start.name,
            StateStatus.idle.name,
            StateStatus.service.name,
        ):
            self._is_reporting = False
            self._attr_native_value = None

        # appliance might report the last value for consumption of previous cycle and it will report 0
        # only after a while, so it is necessary to force 0 until we see the 0 value coming from API, unless
        # we already saw a valid value in this cycle from cache
        elif (
            current_status in (StateStatus.in_use.name, StateStatus.pause.name)
            and not self._is_reporting
            and last_value > 0
        ):
            self._attr_native_value = current_value
            self._is_reporting = True

        elif (
            current_status in (StateStatus.in_use.name, StateStatus.pause.name)
            and not self._is_reporting
            and current_value is not None
            and cast(int, current_value) > 0
        ):
            self._attr_native_value = 0

        # keep value when program ends
        elif current_status == StateStatus.program_ended.name:
            pass

        else:
            self._attr_native_value = current_value
            self._is_reporting = True
