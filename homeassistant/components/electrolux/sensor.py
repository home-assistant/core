"""Sensor entity for Electrolux Integration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, override

from electrolux_group_developer_sdk.appliance_config.cr_config import EXTRA_CAVITY
from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance
from electrolux_group_developer_sdk.feature_constants import (
    AD_TANK_A_DET_LOADED_CAPABILITY,
    AD_TANK_B_DET_LOADED_CAPABILITY,
    AD_TANK_B_SOFT_LOADED_CAPABILITY,
    AIR_FILTER_STATE,
    APPLIANCE_STATE,
    BATTERY,
    CYCLE_PHASE,
    DISPLAY_FOOD_PROBE_TEMPERATURE_C,
    DISPLAY_FOOD_PROBE_TEMPERATURE_F,
    DISPLAY_TEMPERATURE_C,
    DISPLAY_TEMPERATURE_F,
    ECO_LEVEL_CAPABILITY,
    FOOD_PROBE_STATE,
    HOB_HOOD_WINDOW_NOTIFICATION,
    PM_1,
    PM_2_5,
    PM_10,
    REMOTE_CONTROL,
    SOUND_VOLUME,
    TANK_A_DET_LOAD_FOR_NOMINAL_WEIGHT_CAPABILITY,
    TANK_A_RESERVE_CAPABILITY,
    TANK_B_DET_LOAD_FOR_NOMINAL_WEIGHT_CAPABILITY,
    TANK_B_RESERVE_CAPABILITY,
    TARGET_TEMPERATURE_C,
    TARGET_TEMPERATURE_F,
    TVOC,
    WATER_FILTER_STATE,
    WATER_HARDNESS,
    WATER_USAGE_CAPABILITY,
    ZONE_RESIDUAL_HEAT_STATE,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfDensity, UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import ELECTROLUX_TO_HA_TEMPERATURE_UNIT
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import (
    convert_to_snake_case,
    get_submodule_entity_key,
    get_submodule_translation_key,
)

_LOGGER = logging.getLogger(__name__)

APPLIANCE_STATE_KNOWN_VALUES = {
    "alarm",
    "delayed_start",
    "end_of_cycle",
    "idle",
    "off",
    "paused",
    "ready_to_start",
    "running",
}

FOOD_PROBE_STATE_KNOWN_VALUES = {"inserted", "not_inserted"}


@dataclass(frozen=True, kw_only=True)
class ElectroluxSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux sensors."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T], StateType]


@dataclass(frozen=True, kw_only=True)
class ElectroluxEnumSensorDescription[T: ApplianceData](ElectroluxSensorDescription[T]):
    """Custom sensor description for Electrolux sensors."""

    feature_name: str
    known_values: set[str]
    device_class = SensorDeviceClass.ENUM


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux appliance submodule sensors."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    value_fn: Callable[[T, str], StateType]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleEnumSensorDescription[T: ApplianceData](
    ElectroluxSubmoduleSensorDescription[T]
):
    """Custom sensor description for Electrolux appliance submodule sensors."""

    feature_name: str
    known_values: set[str]
    device_class = SensorDeviceClass.ENUM


@dataclass(frozen=True, kw_only=True)
class ElectroluxTemperatureSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux temperature sensors."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T, UnitOfTemperature], float | None]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleTemperatureSensorDescription[T: ApplianceData](
    SensorEntityDescription
):
    """Custom sensor description for Electrolux temperature sensors."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    value_fn: Callable[[T, str, UnitOfTemperature], float | None]


def _get_appliance_state_description[
    T: DWAppliance
    | HBAppliance
    | HDAppliance
    | OVAppliance
    | TDAppliance
    | WDAppliance
    | WMAppliance
]() -> ElectroluxEnumSensorDescription[T]:
    return ElectroluxEnumSensorDescription[T](
        key="appliance_state",
        translation_key="appliance_state",
        device_class=SensorDeviceClass.ENUM,
        exists_fn=lambda appliance: appliance.is_feature_supported(APPLIANCE_STATE),
        value_fn=lambda appliance: appliance.get_current_appliance_state(),
        feature_name=APPLIANCE_STATE,
        known_values=APPLIANCE_STATE_KNOWN_VALUES,
    )


def _get_appliance_state_submodule_description[T: CRAppliance | SOAppliance]() -> (
    ElectroluxSubmoduleEnumSensorDescription[T]
):
    return ElectroluxSubmoduleEnumSensorDescription[T](
        key="appliance_state",
        translation_key="appliance_state",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, APPLIANCE_STATE
        ),
        value_fn=lambda appliance, cavity: appliance.get_current_cavity_appliance_state(
            cavity
        ),
        feature_name=APPLIANCE_STATE,
        known_values=APPLIANCE_STATE_KNOWN_VALUES,
    )


def _get_remote_control_description[
    T: DWAppliance
    | HBAppliance
    | HDAppliance
    | OVAppliance
    | TDAppliance
    | SOAppliance
    | WDAppliance
    | WMAppliance
]() -> ElectroluxEnumSensorDescription[T]:
    return ElectroluxEnumSensorDescription[T](
        key="remote_control",
        translation_key="remote_control",
        device_class=SensorDeviceClass.ENUM,
        exists_fn=lambda appliance: appliance.is_feature_supported(REMOTE_CONTROL),
        value_fn=lambda appliance: appliance.get_current_remote_control(),
        feature_name=REMOTE_CONTROL,
        known_values={
            "disabled",
            "enabled",
            "not_safety_relevant_enabled",
            "temporary_locked",
        },
    )


OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription[OVAppliance], ...] = (
    _get_appliance_state_description(),
    ElectroluxEnumSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        device_class=SensorDeviceClass.ENUM,
        exists_fn=lambda appliance: appliance.is_feature_supported(FOOD_PROBE_STATE),
        value_fn=lambda appliance: appliance.get_current_food_probe_insertion_state(),
        feature_name=FOOD_PROBE_STATE,
        known_values=FOOD_PROBE_STATE_KNOWN_VALUES,
    ),
    _get_remote_control_description(),
)

OVEN_TEMPERATURE_ELECTROLUX_SENSORS: tuple[
    ElectroluxTemperatureSensorDescription[OVAppliance], ...
] = (
    ElectroluxTemperatureSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_FOOD_PROBE_TEMPERATURE_F, DISPLAY_FOOD_PROBE_TEMPERATURE_C]
        ),
        value_fn=lambda appliance, temp_unit: (
            appliance.get_current_display_food_probe_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_food_probe_temperature_c()
        ),
    ),
    ElectroluxTemperatureSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_TEMPERATURE_C, DISPLAY_TEMPERATURE_F]
        ),
        value_fn=lambda appliance, temp_unit: (
            appliance.get_current_display_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_temperature_c()
        ),
    ),
)


STRUCTURED_OVEN_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[SOAppliance], ...
] = (_get_remote_control_description(),)

STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleSensorDescription[SOAppliance], ...
] = (
    _get_appliance_state_submodule_description(),
    ElectroluxSubmoduleEnumSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, FOOD_PROBE_STATE
        ),
        value_fn=lambda appliance, cavity: (
            appliance.get_current_cavity_food_probe_insertion_state(cavity)
        ),
        feature_name=FOOD_PROBE_STATE,
        known_values=FOOD_PROBE_STATE_KNOWN_VALUES,
    ),
)

STRUCTURED_OVEN_CAVITY_TEMPERATURE_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleTemperatureSensorDescription[SOAppliance], ...
] = (
    ElectroluxSubmoduleTemperatureSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, [DISPLAY_FOOD_PROBE_TEMPERATURE_C, DISPLAY_FOOD_PROBE_TEMPERATURE_F]
        ),
        value_fn=lambda appliance, cavity, temp_unit: (
            appliance.get_current_cavity_display_food_probe_temperature_f(cavity)
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_cavity_display_food_probe_temperature_c(cavity)
        ),
    ),
    ElectroluxSubmoduleTemperatureSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, [DISPLAY_TEMPERATURE_C, DISPLAY_TEMPERATURE_F]
        ),
        value_fn=lambda appliance, cavity, temp_unit: (
            appliance.get_current_cavity_display_temperature_f(cavity)
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_cavity_display_temperature_c(cavity)
        ),
    ),
)


CARE_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[DWAppliance | TDAppliance | WDAppliance | WMAppliance],
    ...,
] = (
    _get_appliance_state_description(),
    ElectroluxEnumSensorDescription(
        key="cycle_phase",
        translation_key="cycle_phase",
        exists_fn=lambda appliance: appliance.is_feature_supported(CYCLE_PHASE),
        value_fn=lambda appliance: appliance.get_current_cycle_phase(),
        feature_name=CYCLE_PHASE,
        known_values={
            "ado_drying",
            "anticrease",
            "coldrinse",
            "cool",
            "drain",
            "dry",
            "drying",
            "extrarinse",
            "hotrinse",
            "mainwash",
            "prewash",
            "rinse",
            "spin",
            "steam",
            "unavailable",
            "wash",
        },
    ),
    _get_remote_control_description(),
    ElectroluxEnumSensorDescription(
        key="water_hardness",
        translation_key="water_hardness",
        exists_fn=lambda appliance: appliance.is_feature_supported(WATER_HARDNESS),
        value_fn=lambda appliance: appliance.get_current_water_hardness(),
        feature_name=WATER_HARDNESS,
        known_values={"soft", "medium", "hard"},
    ),
)

WM_WD_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[WDAppliance | WMAppliance], ...
] = (
    ElectroluxSensorDescription(
        key="wm_water_usage",
        translation_key="wm_water_usage",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            WATER_USAGE_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_water_usage()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_eco_level",
        translation_key="wm_eco_level",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            ECO_LEVEL_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_eco_level()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_tank_a_det_load_for_nominal_weight",
        translation_key="wm_tank_a_det_load_for_nominal_weight",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            TANK_A_DET_LOAD_FOR_NOMINAL_WEIGHT_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_tank_a_det_load_for_nominal_weight()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_tank_a_reserve",
        translation_key="wm_tank_a_reserve",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            TANK_A_RESERVE_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_tank_a_reserve()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_tank_b_det_load_for_nominal_weight",
        translation_key="wm_tank_b_det_load_for_nominal_weight",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            TANK_B_DET_LOAD_FOR_NOMINAL_WEIGHT_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_tank_b_det_load_for_nominal_weight()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_tank_b_reserve",
        translation_key="wm_tank_b_reserve",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            TANK_B_RESERVE_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_tank_b_reserve()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_ad_tank_a_det_loaded",
        translation_key="wm_ad_tank_a_det_loaded",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            AD_TANK_A_DET_LOADED_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_ad_tank_a_det_loaded()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_ad_tank_b_det_loaded",
        translation_key="wm_ad_tank_b_det_loaded",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            AD_TANK_B_DET_LOADED_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_ad_tank_b_det_loaded()
        ),
    ),
    ElectroluxSensorDescription(
        key="wm_ad_tank_b_soft_loaded",
        translation_key="wm_ad_tank_b_soft_loaded",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            AD_TANK_B_SOFT_LOADED_CAPABILITY
        ),
        value_fn=lambda appliance: (
            appliance.get_current_f_c_miscellaneous_state_ad_tank_b_soft_loaded()
        ),
    ),
)

REFRIGERATOR_GENERIC_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[CRAppliance], ...
] = (
    ElectroluxEnumSensorDescription(
        key="filter_state_water",
        translation_key="filter_state_water",
        exists_fn=lambda appliance: appliance.is_feature_supported(WATER_FILTER_STATE),
        value_fn=lambda appliance: appliance.get_current_water_filter_state(),
        feature_name=WATER_FILTER_STATE,
        known_values={"buy", "change", "clean", "good"},
    ),
    ElectroluxEnumSensorDescription(
        key="filter_state_air",
        translation_key="filter_state_air",
        exists_fn=lambda appliance: appliance.is_feature_supported(AIR_FILTER_STATE),
        value_fn=lambda appliance: appliance.get_current_air_filter_state(),
        feature_name=AIR_FILTER_STATE,
        known_values={"buy", "change", "clean", "good"},
    ),
)

EXTRA_CAVITY_TEMPERATURE_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleTemperatureSensorDescription[CRAppliance], ...
] = (
    ElectroluxSubmoduleTemperatureSensorDescription(
        key="target_temperature",
        translation_key="target_temperature",
        exists_fn=lambda appliance, submodule: (
            appliance.is_cavity_feature_supported(submodule, TARGET_TEMPERATURE_C)
            or appliance.is_cavity_feature_supported(submodule, TARGET_TEMPERATURE_F)
        ),
        value_fn=lambda appliance, submodule, temp_unit: (
            appliance.get_current_cavity_target_temperature_f(submodule)
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_cavity_target_temperature_c(submodule)
        ),
    ),
)

FREEZER_FRIDGE_ICE_MAKER_EXTRA_CAVITY_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleSensorDescription[CRAppliance], ...
] = (_get_appliance_state_submodule_description(),)

HOOD_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription[HDAppliance], ...] = (
    _get_appliance_state_description(),
    ElectroluxSensorDescription(
        key="sound_volume",
        translation_key="sound_volume",
        exists_fn=lambda appliance: appliance.is_feature_supported(SOUND_VOLUME),
        value_fn=lambda appliance: appliance.get_current_sound_volume(),
    ),
    _get_remote_control_description(),
)

HOB_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription[HBAppliance], ...] = (
    _get_appliance_state_description(),
    _get_remote_control_description(),
    ElectroluxEnumSensorDescription(
        key="hob_hood_window_notification",
        translation_key="hob_hood_window_notification",
        exists_fn=lambda appliance: appliance.is_hood_feature_supported(
            HOB_HOOD_WINDOW_NOTIFICATION
        ),
        value_fn=lambda appliance: appliance.get_current_hob_hood_window_notification(),
        feature_name=HOB_HOOD_WINDOW_NOTIFICATION,
        known_values={"none", "opening_required"},
    ),
)

HOB_ZONE_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleSensorDescription[HBAppliance], ...
] = (
    ElectroluxSubmoduleEnumSensorDescription(
        key="zone_residual_heat_state",
        translation_key="zone_residual_heat_state",
        exists_fn=lambda appliance, hob_zone: appliance.is_hob_zone_feature_supported(
            hob_zone, ZONE_RESIDUAL_HEAT_STATE
        ),
        value_fn=lambda appliance, hob_zone: (
            appliance.get_current_zone_residual_heat_state(hob_zone)
        ),
        feature_name=ZONE_RESIDUAL_HEAT_STATE,
        known_values={"high", "low", "middle", "no"},
    ),
)

VACUUM_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription[RVCAppliance], ...] = (
    ElectroluxSensorDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda appliance: appliance.is_feature_supported(BATTERY),
        value_fn=lambda appliance: appliance.get_battery_percentage(),
    ),
)


def _is_air_quality_sensor_supported(
    appliance: APAppliance, air_quality_key: str
) -> bool:
    """Check if the air quality sensor is supported for the given property."""
    air_quality_map = appliance.get_air_quality_map() or {}
    if air_quality_key not in air_quality_map:
        return False
    air_quality_property = air_quality_map[air_quality_key]

    if TYPE_CHECKING:
        assert appliance.state is not None
    appliance_state = appliance.state.properties.get("reported", {})

    return appliance_state and air_quality_property in appliance_state


AIR_PURIFIER_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[APAppliance], ...
] = (
    ElectroluxSensorDescription(
        key="pm_1",
        translation_key="pm_1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        exists_fn=lambda appliance: _is_air_quality_sensor_supported(appliance, PM_1),
        value_fn=lambda appliance: appliance.get_current_air_quality(PM_1),
    ),
    ElectroluxSensorDescription(
        key="pm_2_5",
        translation_key="pm_2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        exists_fn=lambda appliance: _is_air_quality_sensor_supported(appliance, PM_2_5),
        value_fn=lambda appliance: appliance.get_current_air_quality(PM_2_5),
    ),
    ElectroluxSensorDescription(
        key="pm_10",
        translation_key="pm_10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        exists_fn=lambda appliance: _is_air_quality_sensor_supported(appliance, PM_10),
        value_fn=lambda appliance: appliance.get_current_air_quality(PM_10),
    ),
    ElectroluxSensorDescription(
        key="tvoc",
        translation_key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
        exists_fn=lambda appliance: _is_air_quality_sensor_supported(appliance, TVOC),
        value_fn=lambda appliance: appliance.get_current_air_quality(TVOC),
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in OVEN_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxTemperatureSensor(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        cavities = appliance_data.get_supported_cavities()
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in STRUCTURED_OVEN_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxSubmoduleSensor(appliance_data, coordinator, cavity, description)
            for description in STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS
            for cavity in cavities
            if description.exists_fn(appliance_data, cavity)
        )

        entities.extend(
            ElectroluxSubmoduleTemperatureSensor(
                appliance_data, coordinator, cavity, description
            )
            for description in STRUCTURED_OVEN_CAVITY_TEMPERATURE_ELECTROLUX_SENSORS
            for cavity in cavities
            if description.exists_fn(appliance_data, cavity)
        )

    if isinstance(
        appliance_data, DWAppliance | TDAppliance | WDAppliance | WMAppliance
    ):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in CARE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, WDAppliance | WMAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in WM_WD_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, CRAppliance):
        cavities = appliance_data.get_supported_cavities()

        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in REFRIGERATOR_GENERIC_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxSubmoduleSensor(appliance_data, coordinator, cavity, description)
            for cavity in cavities
            for description in FREEZER_FRIDGE_ICE_MAKER_EXTRA_CAVITY_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data, cavity)
        )

        entities.extend(
            ElectroluxSubmoduleTemperatureSensor(
                appliance_data, coordinator, EXTRA_CAVITY, description
            )
            for description in EXTRA_CAVITY_TEMPERATURE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data, EXTRA_CAVITY)
        )

    if isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in HOOD_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, HBAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in HOB_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxSubmoduleSensor(
                appliance_data, coordinator, hob_zone, description
            )
            for hob_zone in appliance_data.get_available_hob_zone()
            for description in HOB_ZONE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data, hob_zone)
        )

    if isinstance(appliance_data, RVCAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in VACUUM_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, APAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in AIR_PURIFIER_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set sensor for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseSensor[T: ApplianceData](
    ElectroluxBaseEntity[T], SensorEntity, ABC
):
    """Abstract base class for sensors of the Electrolux integration."""

    @override
    def _update_attr_state(self) -> bool:
        new_value = self._get_value()

        if self._attr_native_value != new_value:
            self._attr_native_value = new_value
            return True

        return False

    @abstractmethod
    def _get_value(self) -> StateType:
        raise NotImplementedError


class ElectroluxSensor[T: ApplianceData](ElectroluxBaseSensor[T]):
    """Representation of a generic sensor for Electrolux appliances."""

    entity_description: ElectroluxSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

        if isinstance(description, ElectroluxEnumSensorDescription):
            options = appliance_data.get_feature_state_string_options(
                description.feature_name
            )
            snake_case_options = [
                snake_case_option
                for option in options
                if (snake_case_option := convert_to_snake_case(option))
                in description.known_values
            ]

            if len(snake_case_options) > 0:
                self._attr_options = snake_case_options

    @override
    def _get_value(self) -> StateType:
        value = self.entity_description.value_fn(self._appliance_data)

        if isinstance(value, str) and isinstance(
            self.entity_description, ElectroluxEnumSensorDescription
        ):
            value = convert_to_snake_case(value)
            if self.entity_description.known_values:
                value = _map_to_known_value(
                    self.entity_description.known_values,
                    self.entity_description.key,
                    value,
                )

        return value


class ElectroluxTemperatureSensor[T: CRAppliance | OVAppliance](
    ElectroluxBaseSensor[T]
):
    """Representation of a temperature sensor for Electrolux appliances."""

    entity_description: ElectroluxTemperatureSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxTemperatureSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, description.key)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self.entity_description = description

    @override
    def _get_value(self) -> StateType:
        temp_unit = _get_temperature_unit(self._appliance_data)
        temp_value = self.entity_description.value_fn(self._appliance_data, temp_unit)
        if temp_value is None:
            return None
        return TemperatureConverter.convert(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )


class ElectroluxBaseSubmoduleSensor[T: ApplianceData](ElectroluxBaseSensor[T]):
    """Representation of a generic sensor for Electrolux appliances with submodules."""

    _submodule: str

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        submodule: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        entity_key = get_submodule_entity_key(submodule, description)
        translation_key = get_submodule_translation_key(submodule, description)

        super().__init__(appliance_data, coordinator, entity_key)
        self._submodule = submodule
        self._attr_translation_key = translation_key


class ElectroluxSubmoduleSensor[T: ApplianceData](ElectroluxBaseSubmoduleSensor[T]):
    """Representation of a generic sensor for Electrolux appliances with submodules."""

    entity_description: ElectroluxSubmoduleSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        submodule: str,
        description: ElectroluxSubmoduleSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, submodule, description)
        self.entity_description = description

        if isinstance(description, ElectroluxSubmoduleEnumSensorDescription):
            options = _get_submodule_options(
                submodule, description.feature_name, appliance_data
            )
            snake_case_options = [
                snake_case_option
                for option in options
                if (snake_case_option := convert_to_snake_case(option))
                in description.known_values
            ]

            if len(snake_case_options) > 0:
                self._attr_options = snake_case_options

    @override
    def _get_value(self) -> StateType:
        description = self.entity_description

        value = description.value_fn(self._appliance_data, self._submodule)
        if isinstance(value, str) and isinstance(
            description, ElectroluxSubmoduleEnumSensorDescription
        ):
            entity_key = f"{convert_to_snake_case(self._submodule)}_{description.key}"
            value = convert_to_snake_case(value)
            if description.known_values:
                value = _map_to_known_value(
                    description.known_values,
                    entity_key,
                    value,
                )

        return value


class ElectroluxSubmoduleTemperatureSensor[T: CRAppliance | SOAppliance](
    ElectroluxBaseSubmoduleSensor[T]
):
    """Representation of a temperature sensor for Electrolux appliances with submodules."""

    entity_description: ElectroluxSubmoduleTemperatureSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        submodule: str,
        description: ElectroluxSubmoduleTemperatureSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, submodule, description)
        self.entity_description = description

    @override
    def _get_value(self) -> StateType:
        temp_unit = _get_temperature_unit(self._appliance_data)
        temp_value = self.entity_description.value_fn(
            self._appliance_data, self._submodule, temp_unit
        )
        if temp_value is None:
            return None
        return TemperatureConverter.convert(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )


def _map_to_known_value(
    known_values: set[str], entity_key: str, value: str
) -> str | None:
    """Return provided value if it is known, otherwise log warn message and return None."""
    if value not in known_values:
        _LOGGER.warning(
            "An unknown value %s was reported for a sensor of the Electrolux integration. "
            "Please report it for the integration, and include the following information: "
            'entity key="%s", reported value="%s"',
            value,
            entity_key,
            value,
        )
        return None
    return value


def _get_submodule_options(
    submodule: str, feature_name: str, appliance_data: ApplianceData
) -> list[str]:
    if isinstance(appliance_data, SOAppliance):
        return appliance_data.get_cavity_feature_state_string_options(
            submodule, feature_name
        )
    if isinstance(appliance_data, HBAppliance):
        return appliance_data.get_hob_zone_feature_state_string_options(
            submodule, feature_name
        )
    if isinstance(appliance_data, CRAppliance):
        return appliance_data.get_cavity_feature_state_string_options(
            submodule, feature_name
        )

    return []


def _get_temperature_unit(
    appliance: CRAppliance | OVAppliance | SOAppliance,
) -> UnitOfTemperature:
    temp_unit = appliance.get_current_temperature_unit()

    if temp_unit is not None:
        temp_unit = temp_unit.upper()

    return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(temp_unit, UnitOfTemperature.CELSIUS)
