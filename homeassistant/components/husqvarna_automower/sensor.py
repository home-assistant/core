"""Creates the sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from aioautomower.model import MowerAttributes, MowerModes, RestrictedReasons

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)

ERROR_KEY_LIST = [
    "no_error",
    "alarm_mower_in_motion",
    "alarm_mower_lifted",
    "alarm_mower_stopped",
    "alarm_mower_switched_off",
    "alarm_mower_tilted",
    "alarm_outside_geofence",
    "angular_sensor_problem",
    "battery_problem",
    "battery_problem",
    "battery_restriction_due_to_ambient_temperature",
    "can_error",
    "charging_current_too_high",
    "charging_station_blocked",
    "charging_system_problem",
    "charging_system_problem",
    "collision_sensor_defect",
    "collision_sensor_error",
    "collision_sensor_problem_front",
    "collision_sensor_problem_rear",
    "com_board_not_available",
    "communication_circuit_board_sw_must_be_updated",
    "complex_working_area",
    "connection_changed",
    "connection_not_changed",
    "connectivity_problem",
    "connectivity_problem",
    "connectivity_problem",
    "connectivity_problem",
    "connectivity_problem",
    "connectivity_problem",
    "connectivity_settings_restored",
    "cutting_drive_motor_1_defect",
    "cutting_drive_motor_2_defect",
    "cutting_drive_motor_3_defect",
    "cutting_height_blocked",
    "cutting_height_problem",
    "cutting_height_problem_curr",
    "cutting_height_problem_dir",
    "cutting_height_problem_drive",
    "cutting_motor_problem",
    "cutting_stopped_slope_too_steep",
    "cutting_system_blocked",
    "cutting_system_blocked",
    "cutting_system_imbalance_warning",
    "cutting_system_major_imbalance",
    "destination_not_reachable",
    "difficult_finding_home",
    "docking_sensor_defect",
    "electronic_problem",
    "empty_battery",
    "folding_cutting_deck_sensor_defect",
    "folding_sensor_activated",
    "geofence_problem",
    "geofence_problem",
    "gps_navigation_problem",
    "guide_1_not_found",
    "guide_2_not_found",
    "guide_3_not_found",
    "guide_calibration_accomplished",
    "guide_calibration_failed",
    "high_charging_power_loss",
    "high_internal_power_loss",
    "high_internal_temperature",
    "internal_voltage_error",
    "invalid_battery_combination_invalid_combination_of_different_battery_types",
    "invalid_sub_device_combination",
    "invalid_system_configuration",
    "left_brush_motor_overloaded",
    "lift_sensor_defect",
    "lifted",
    "limited_cutting_height_range",
    "limited_cutting_height_range",
    "loop_sensor_defect",
    "loop_sensor_problem_front",
    "loop_sensor_problem_left",
    "loop_sensor_problem_rear",
    "loop_sensor_problem_right",
    "low_battery",
    "memory_circuit_problem",
    "mower_lifted",
    "mower_tilted",
    "no_accurate_position_from_satellites",
    "no_confirmed_position",
    "no_drive",
    "no_loop_signal",
    "no_power_in_charging_station",
    "no_response_from_charger",
    "outside_working_area",
    "poor_signal_quality",
    "reference_station_communication_problem",
    "right_brush_motor_overloaded",
    "safety_function_faulty",
    "settings_restored",
    "sim_card_locked",
    "sim_card_locked",
    "sim_card_locked",
    "sim_card_locked",
    "sim_card_not_found",
    "sim_card_requires_pin",
    "slipped_mower_has_slipped_situation_not_solved_with_moving_pattern",
    "slope_too_steep",
    "sms_could_not_be_sent",
    "stop_button_problem",
    "stuck_in_charging_station",
    "switch_cord_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "temporary_battery_problem",
    "tilt_sensor_problem",
    "too_high_discharge_current",
    "too_high_internal_current",
    "trapped",
    "ultrasonic_problem",
    "ultrasonic_sensor_1_defect",
    "ultrasonic_sensor_2_defect",
    "ultrasonic_sensor_3_defect",
    "ultrasonic_sensor_4_defect",
    "unexpected_cutting_height_adj",
    "unexpected_error",
    "upside_down",
    "weak_gps_signal",
    "wheel_drive_problem_left",
    "wheel_drive_problem_rear_left",
    "wheel_drive_problem_rear_right",
    "wheel_drive_problem_right",
    "wheel_motor_blocked_left",
    "wheel_motor_blocked_rear_left",
    "wheel_motor_blocked_rear_right",
    "wheel_motor_blocked_right",
    "wheel_motor_overloaded_left",
    "wheel_motor_overloaded_rear_left",
    "wheel_motor_overloaded_rear_right",
    "wheel_motor_overloaded_right",
    "work_area_not_valid",
    "wrong_loop_signal",
    "wrong_pin_code",
    "zone_generator_problem",
]

RESTRICTED_REASONS: list = [
    RestrictedReasons.ALL_WORK_AREAS_COMPLETED.lower(),
    RestrictedReasons.DAILY_LIMIT.lower(),
    RestrictedReasons.EXTERNAL.lower(),
    RestrictedReasons.FOTA.lower(),
    RestrictedReasons.FROST.lower(),
    RestrictedReasons.NONE.lower(),
    RestrictedReasons.NOT_APPLICABLE.lower(),
    RestrictedReasons.PARK_OVERRIDE.lower(),
    RestrictedReasons.SENSOR.lower(),
    RestrictedReasons.WEEK_SCHEDULE.lower(),
]


@dataclass(frozen=True, kw_only=True)
class AutomowerSensorEntityDescription(SensorEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    value_fn: Callable[[MowerAttributes], StateType | datetime]


SENSOR_TYPES: tuple[AutomowerSensorEntityDescription, ...] = (
    AutomowerSensorEntityDescription(
        key="battery_percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.battery.battery_percent,
    ),
    AutomowerSensorEntityDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=[option.lower() for option in list(MowerModes)],
        value_fn=(
            lambda data: data.mower.mode.lower()
            if data.mower.mode != MowerModes.UNKNOWN
            else None
        ),
    ),
    AutomowerSensorEntityDescription(
        key="cutting_blade_usage_time",
        translation_key="cutting_blade_usage_time",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.cutting_blade_usage_time is not None,
        value_fn=lambda data: data.statistics.cutting_blade_usage_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_charging_time",
        translation_key="total_charging_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.total_charging_time is not None,
        value_fn=lambda data: data.statistics.total_charging_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_cutting_time",
        translation_key="total_cutting_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.total_cutting_time is not None,
        value_fn=lambda data: data.statistics.total_cutting_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_running_time",
        translation_key="total_running_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.total_running_time is not None,
        value_fn=lambda data: data.statistics.total_running_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_searching_time",
        translation_key="total_searching_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.total_searching_time is not None,
        value_fn=lambda data: data.statistics.total_searching_time,
    ),
    AutomowerSensorEntityDescription(
        key="number_of_charging_cycles",
        translation_key="number_of_charging_cycles",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        exists_fn=lambda data: data.statistics.number_of_charging_cycles is not None,
        value_fn=lambda data: data.statistics.number_of_charging_cycles,
    ),
    AutomowerSensorEntityDescription(
        key="number_of_collisions",
        translation_key="number_of_collisions",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        exists_fn=lambda data: data.statistics.number_of_collisions is not None,
        value_fn=lambda data: data.statistics.number_of_collisions,
    ),
    AutomowerSensorEntityDescription(
        key="total_drive_distance",
        translation_key="total_drive_distance",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        exists_fn=lambda data: data.statistics.total_drive_distance is not None,
        value_fn=lambda data: data.statistics.total_drive_distance,
    ),
    AutomowerSensorEntityDescription(
        key="next_start_timestamp",
        translation_key="next_start_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.planner.next_start_datetime,
    ),
    AutomowerSensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: (
            "no_error" if data.mower.error_key is None else data.mower.error_key
        ),
        options=ERROR_KEY_LIST,
    ),
    AutomowerSensorEntityDescription(
        key="restricted_reason",
        translation_key="restricted_reason",
        device_class=SensorDeviceClass.ENUM,
        options=RESTRICTED_REASONS,
        value_fn=lambda data: data.planner.restricted_reason.lower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerSensorEntity(mower_id, coordinator, description)
        for mower_id in coordinator.data
        for description in SENSOR_TYPES
        if description.exists_fn(coordinator.data[mower_id])
    )


class AutomowerSensorEntity(AutomowerBaseEntity, SensorEntity):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerSensorEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerSensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.mower_attributes)
