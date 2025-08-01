"""Sensor platform for Miele integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final, cast

from pymiele import MieleDevice, MieleTemperature

from homeassistant.components.sensor import (
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DISABLED_TEMP_ENTITIES,
    DOMAIN,
    STATE_PROGRAM_ID,
    STATE_PROGRAM_PHASE,
    STATE_STATUS_TAGS,
    MieleAppliance,
    PlatePowerStep,
    StateDryingStep,
    StateProgramType,
    StateStatus,
)
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

DEFAULT_PLATE_COUNT = 4

PLATE_COUNT = {
    "KM7678": 6,
    "KM7697": 6,
    "KM7878": 6,
    "KM7897": 6,
    "KMDA7633": 5,
    "KMDA7634": 5,
    "KMDA7774": 5,
    "KMX": 6,
}


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


@dataclass(frozen=True, kw_only=True)
class MieleSensorDescription(SensorEntityDescription):
    """Class describing Miele sensor entities."""

    value_fn: Callable[[MieleDevice], StateType]
    zone: int | None = None
    unique_id_fn: Callable[[str, MieleSensorDescription], str] | None = None


@dataclass
class MieleSensorDefinition:
    """Class for defining sensor entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleSensorDescription


SENSOR_TYPES: Final[tuple[MieleSensorDefinition, ...]] = (
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
            options=sorted(set(STATE_STATUS_TAGS.values())),
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
                lambda value: value.energy_forecast * 100
                if value.energy_forecast is not None
                else None
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
                lambda value: value.water_forecast * 100
                if value.water_forecast is not None
                else None
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
            native_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfTime.HOURS,
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
                unique_id_fn=lambda device_id,
                description: f"{device_id}-{description.key}-{description.zone}",
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
            value_fn=lambda value: StateDryingStep(
                cast(int, value.state_drying_step)
            ).name,
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    added_devices: set[str] = set()  # device_id
    added_entities: set[str] = set()  # unique_id

    def _get_entity_class(definition: MieleSensorDefinition) -> type[MieleSensor]:
        """Get the entity class for the sensor."""
        return {
            "state_status": MieleStatusSensor,
            "state_program_id": MieleProgramIdSensor,
            "state_program_phase": MielePhaseSensor,
            "state_plate_step": MielePlateSensor,
        }.get(definition.description.key, MieleSensor)

    def _is_entity_registered(unique_id: str) -> bool:
        """Check if the entity is already registered."""
        entity_registry = er.async_get(hass)
        return any(
            entry.platform == DOMAIN and entry.unique_id == unique_id
            for entry in entity_registry.entities.values()
        )

    def _is_sensor_enabled(
        definition: MieleSensorDefinition,
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
                if not _is_sensor_enabled(definition, device, unique_id):
                    continue

                added_entities.add(unique_id)
                entities.append(
                    entity_class(coordinator, device_id, definition.description)
                )
        async_add_entities(entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_devices))
    _async_add_devices()


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
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)


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
        return STATE_STATUS_TAGS.get(StateStatus(self.device.state_status))

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""
        # This sensor should always be available
        return True


class MielePhaseSensor(MieleSensor):
    """Representation of the program phase sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        ret_val = STATE_PROGRAM_PHASE.get(self.device.device_type, {}).get(
            self.device.state_program_phase
        )
        if ret_val is None:
            _LOGGER.debug(
                "Unknown program phase: %s on device type: %s",
                self.device.state_program_phase,
                self.device.device_type,
            )
        return ret_val

    @property
    def options(self) -> list[str]:
        """Return the options list for the actual device type."""
        return sorted(
            set(STATE_PROGRAM_PHASE.get(self.device.device_type, {}).values())
        )


class MieleProgramIdSensor(MieleSensor):
    """Representation of the program id sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        ret_val = STATE_PROGRAM_ID.get(self.device.device_type, {}).get(
            self.device.state_program_id
        )
        if ret_val is None:
            _LOGGER.debug(
                "Unknown program id: %s on device type: %s",
                self.device.state_program_id,
                self.device.device_type,
            )
        return ret_val

    @property
    def options(self) -> list[str]:
        """Return the options list for the actual device type."""
        return sorted(set(STATE_PROGRAM_ID.get(self.device.device_type, {}).values()))
