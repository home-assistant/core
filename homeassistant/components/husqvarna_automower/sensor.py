"""Creates the sensor entities for the mower."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from operator import attrgetter
from typing import TYPE_CHECKING, Any

from aioautomower.model import (
    ExternalReasons,
    InactiveReasons,
    MowerAttributes,
    MowerModes,
    RestrictedReasons,
    WorkArea,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AutomowerConfigEntry
from .const import ERROR_KEYS, ERROR_STATES
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import (
    AutomowerBaseEntity,
    WorkAreaAvailableEntity,
    _work_area_translation_key,
)

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

ATTR_WORK_AREA_ID_ASSIGNMENT = "work_area_id_assignment"

ERROR_KEY_LIST = sorted(
    set(ERROR_KEYS) | {state.lower() for state in ERROR_STATES} | {"no_error"}
)

INACTIVE_REASONS: list = [
    InactiveReasons.NONE,
    InactiveReasons.PLANNING,
    InactiveReasons.SEARCHING_FOR_SATELLITES,
]


RESTRICTED_REASONS: list = [
    RestrictedReasons.ALL_WORK_AREAS_COMPLETED,
    RestrictedReasons.DAILY_LIMIT,
    RestrictedReasons.EXTERNAL,
    RestrictedReasons.FOTA,
    RestrictedReasons.FROST,
    RestrictedReasons.NONE,
    RestrictedReasons.NOT_APPLICABLE,
    RestrictedReasons.PARK_OVERRIDE,
    RestrictedReasons.SENSOR,
    RestrictedReasons.WEEK_SCHEDULE,
    ExternalReasons.AMAZON_ALEXA,
    ExternalReasons.DEVELOPER_PORTAL,
    ExternalReasons.GARDENA_SMART_SYSTEM,
    ExternalReasons.GOOGLE_ASSISTANT,
    ExternalReasons.HOME_ASSISTANT,
    ExternalReasons.IFTTT,
    ExternalReasons.IFTTT_APPLETS,
    ExternalReasons.IFTTT_CALENDAR_CONNECTION,
    ExternalReasons.SMART_ROUTINE,
    ExternalReasons.SMART_ROUTINE_FROST_GUARD,
    ExternalReasons.SMART_ROUTINE_RAIN_GUARD,
    ExternalReasons.SMART_ROUTINE_WILDLIFE_PROTECTION,
]

STATE_NO_WORK_AREA_ACTIVE = "no_work_area_active"


@callback
def _get_restricted_reason(data: MowerAttributes) -> str:
    """Return the restricted reason.

    If there is an external reason, return that instead, if it's available.
    """
    if (
        data.planner.restricted_reason == RestrictedReasons.EXTERNAL
        and data.planner.external_reason is not None
    ):
        return data.planner.external_reason
    return data.planner.restricted_reason


@callback
def _get_work_area_names(data: MowerAttributes) -> list[str]:
    """Return a list with all work area names."""
    if TYPE_CHECKING:
        # Sensor does not get created if it is None
        assert data.work_areas is not None
    work_area_list = [
        data.work_areas[work_area_id].name for work_area_id in data.work_areas
    ]
    work_area_list.append(STATE_NO_WORK_AREA_ACTIVE)
    return work_area_list


@callback
def _get_current_work_area_name(data: MowerAttributes) -> str:
    """Return the name of the current work area."""
    if TYPE_CHECKING:
        # Sensor does not get created if values are None
        assert data.work_areas is not None
    if (
        data.mower.work_area_id is not None
        and data.mower.work_area_id in data.work_areas
    ):
        return data.work_areas[data.mower.work_area_id].name

    return STATE_NO_WORK_AREA_ACTIVE


@callback
def _get_remaining_charging_time(data: MowerAttributes) -> int | None:
    if data.battery.remaining_charging_time is not None:
        return int(data.battery.remaining_charging_time.total_seconds())
    return None


@callback
def _get_current_work_area_dict(data: MowerAttributes) -> Mapping[str, Any]:
    """Return the name of the current work area."""
    if TYPE_CHECKING:
        # Sensor does not get created if it is None
        assert data.work_areas is not None
    return {ATTR_WORK_AREA_ID_ASSIGNMENT: data.work_area_dict}


@callback
def _get_error_string(data: MowerAttributes) -> str:
    """Return the error key, if not provided the mower state or `no error`."""
    if data.mower.error_key is not None:
        return data.mower.error_key
    if data.mower.state in ERROR_STATES:
        return data.mower.state.lower()
    return "no_error"


@dataclass(frozen=True, kw_only=True)
class AutomowerSensorEntityDescription(SensorEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[MowerAttributes], Mapping[str, Any] | None] = (
        lambda _: None
    )
    option_fn: Callable[[MowerAttributes], list[str] | None] = lambda _: None
    value_fn: Callable[[MowerAttributes], StateType | datetime]


MOWER_SENSOR_TYPES: tuple[AutomowerSensorEntityDescription, ...] = (
    AutomowerSensorEntityDescription(
        key="battery_percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=attrgetter("battery.battery_percent"),
    ),
    AutomowerSensorEntityDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        option_fn=lambda data: list(MowerModes),
        value_fn=(
            lambda data: data.mower.mode
            if data.mower.mode != MowerModes.UNKNOWN
            else None
        ),
    ),
    AutomowerSensorEntityDescription(
        key="cutting_blade_usage_time",
        translation_key="cutting_blade_usage_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.cutting_blade_usage_time is not None,
        value_fn=attrgetter("statistics.cutting_blade_usage_time"),
    ),
    AutomowerSensorEntityDescription(
        key="downtime",
        translation_key="downtime",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.downtime is not None,
        value_fn=attrgetter("statistics.downtime"),
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
        value_fn=attrgetter("statistics.total_charging_time"),
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
        value_fn=attrgetter("statistics.total_cutting_time"),
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
        value_fn=attrgetter("statistics.total_running_time"),
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
        value_fn=attrgetter("statistics.total_searching_time"),
    ),
    AutomowerSensorEntityDescription(
        key="number_of_charging_cycles",
        translation_key="number_of_charging_cycles",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        exists_fn=lambda data: data.statistics.number_of_charging_cycles is not None,
        value_fn=attrgetter("statistics.number_of_charging_cycles"),
    ),
    AutomowerSensorEntityDescription(
        key="number_of_collisions",
        translation_key="number_of_collisions",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL,
        exists_fn=lambda data: data.statistics.number_of_collisions is not None,
        value_fn=attrgetter("statistics.number_of_collisions"),
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
        value_fn=attrgetter("statistics.total_drive_distance"),
    ),
    AutomowerSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.uptime is not None,
        value_fn=attrgetter("statistics.uptime"),
    ),
    AutomowerSensorEntityDescription(
        key="next_start_timestamp",
        translation_key="next_start_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=attrgetter("planner.next_start_datetime"),
    ),
    AutomowerSensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=SensorDeviceClass.ENUM,
        option_fn=lambda data: ERROR_KEY_LIST,
        value_fn=_get_error_string,
    ),
    AutomowerSensorEntityDescription(
        key="restricted_reason",
        translation_key="restricted_reason",
        device_class=SensorDeviceClass.ENUM,
        option_fn=lambda data: RESTRICTED_REASONS,
        value_fn=_get_restricted_reason,
    ),
    AutomowerSensorEntityDescription(
        key="inactive_reason",
        translation_key="inactive_reason",
        exists_fn=lambda data: data.capabilities.work_areas,
        device_class=SensorDeviceClass.ENUM,
        option_fn=lambda data: INACTIVE_REASONS,
        value_fn=attrgetter("mower.inactive_reason"),
    ),
    AutomowerSensorEntityDescription(
        key="work_area",
        translation_key="work_area",
        device_class=SensorDeviceClass.ENUM,
        exists_fn=lambda data: data.capabilities.work_areas,
        extra_state_attributes_fn=_get_current_work_area_dict,
        option_fn=_get_work_area_names,
        value_fn=_get_current_work_area_name,
    ),
    AutomowerSensorEntityDescription(
        key="remaining_charging_time",
        translation_key="remaining_charging_time",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        value_fn=_get_remaining_charging_time,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)


@dataclass(frozen=True, kw_only=True)
class WorkAreaSensorEntityDescription(SensorEntityDescription):
    """Describes the work area sensor entities."""

    exists_fn: Callable[[WorkArea], bool] = lambda _: True
    value_fn: Callable[[WorkArea], StateType | datetime]
    translation_key_fn: Callable[[int, str], str]


WORK_AREA_SENSOR_TYPES: tuple[WorkAreaSensorEntityDescription, ...] = (
    WorkAreaSensorEntityDescription(
        key="progress",
        translation_key_fn=_work_area_translation_key,
        exists_fn=lambda data: data.progress is not None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=attrgetter("progress"),
    ),
    WorkAreaSensorEntityDescription(
        key="last_time_completed",
        translation_key_fn=_work_area_translation_key,
        exists_fn=lambda data: data.last_time_completed is not None,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=attrgetter("last_time_completed"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.work_areas:
            _work_areas = coordinator.data[mower_id].work_areas
            if _work_areas is not None:
                entities.extend(
                    WorkAreaSensorEntity(
                        mower_id, coordinator, description, work_area_id
                    )
                    for description in WORK_AREA_SENSOR_TYPES
                    for work_area_id in _work_areas
                    if description.exists_fn(_work_areas[work_area_id])
                )
        entities.extend(
            AutomowerSensorEntity(mower_id, coordinator, description)
            for description in MOWER_SENSOR_TYPES
            if description.exists_fn(coordinator.data[mower_id])
        )
    async_add_entities(entities)

    def _async_add_new_work_areas(mower_id: str, work_area_ids: set[int]) -> None:
        mower_data = coordinator.data[mower_id]
        if mower_data.work_areas is None:
            return

        async_add_entities(
            WorkAreaSensorEntity(mower_id, coordinator, description, work_area_id)
            for description in WORK_AREA_SENSOR_TYPES
            for work_area_id in work_area_ids
            if work_area_id in mower_data.work_areas
            and description.exists_fn(mower_data.work_areas[work_area_id])
        )

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerSensorEntity(mower_id, coordinator, description)
            for mower_id in mower_ids
            for description in MOWER_SENSOR_TYPES
            if description.exists_fn(coordinator.data[mower_id])
        )
        for mower_id in mower_ids:
            mower_data = coordinator.data[mower_id]
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None:
                _async_add_new_work_areas(
                    mower_id,
                    set(mower_data.work_areas.keys()),
                )

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    coordinator.new_areas_callbacks.append(_async_add_new_work_areas)


class AutomowerSensorEntity(AutomowerBaseEntity, SensorEntity):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerSensorEntityDescription
    _unrecorded_attributes = frozenset({ATTR_WORK_AREA_ID_ASSIGNMENT})

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

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.option_fn(self.mower_attributes)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self.entity_description.extra_state_attributes_fn(self.mower_attributes)

    @property
    def available(self) -> bool:
        """Return the available attribute of the entity."""
        return super().available and self.native_value is not None


class WorkAreaSensorEntity(WorkAreaAvailableEntity, SensorEntity):
    """Defining the Work area sensors with WorkAreaSensorEntityDescription."""

    entity_description: WorkAreaSensorEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: WorkAreaSensorEntityDescription,
        work_area_id: int,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, coordinator, work_area_id)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{work_area_id}_{description.key}"
        self._attr_translation_placeholders = {
            "work_area": self.work_area_attributes.name
        }

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.work_area_attributes)

    @property
    def translation_key(self) -> str:
        """Return the translation key of the work area."""
        return self.entity_description.translation_key_fn(
            self.work_area_id, self.entity_description.key
        )
