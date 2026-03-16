"""Support for Litter-Robot sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, LitterRobot5, Pet, Robot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity, _WhiskerEntityT

PARALLEL_UPDATES = 0
MAX_HISTORY_ENTRIES = 20


def _start_of_local_week() -> datetime:
    """Return the start of the current local week (Monday)."""
    today = dt_util.start_of_local_day()
    return today - timedelta(days=today.weekday())


def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


@dataclass(frozen=True, kw_only=True)
class RobotSensorEntityDescription(SensorEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    last_reset_fn: Callable[[], datetime | None] = lambda: None
    value_fn: Callable[[_WhiskerEntityT], float | datetime | str | None]


ROBOT_SENSOR_MAP: dict[
    type[Robot] | tuple[type[Robot], ...], list[RobotSensorEntityDescription]
] = {
    LitterRobot: [
        RobotSensorEntityDescription[LitterRobot](
            key="waste_drawer_level",
            translation_key="waste_drawer",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.waste_drawer_level,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_start_time",
            translation_key="sleep_mode_start_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=(
                lambda robot: (
                    robot.sleep_mode_start_time if robot.sleep_mode_enabled else None
                )
            ),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_end_time",
            translation_key="sleep_mode_end_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=(
                lambda robot: (
                    robot.sleep_mode_end_time if robot.sleep_mode_enabled else None
                )
            ),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="last_seen",
            translation_key="last_seen",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda robot: robot.last_seen,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="status_code",
            translation_key="status_code",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
            options=[
                "br",
                "ccc",
                "ccp",
                "cd",
                "csf",
                "csi",
                "cst",
                "df1",
                "df2",
                "dfs",
                "dhf",
                "dpf",
                "ec",
                "hpf",
                "off",
                "offline",
                "otf",
                "p",
                "pd",
                "pwrd",
                "pwru",
                "rdy",
                "scf",
                "sdf",
                "spf",
            ],
            value_fn=(
                lambda robot: status.lower() if (status := robot.status_code) else None
            ),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="total_cycles",
            translation_key="total_cycles",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda robot: robot.cycle_count,
        ),
    ],
    LitterRobot4: [
        RobotSensorEntityDescription[LitterRobot4](
            key="hopper_status",
            translation_key="hopper_status",
            device_class=SensorDeviceClass.ENUM,
            options=[
                "enabled",
                "disabled",
                "motor_fault_short",
                "motor_ot_amps",
                "motor_disconnected",
                "empty",
            ],
            value_fn=(
                lambda robot: (
                    status.name.lower() if (status := robot.hopper_status) else None
                )
            ),
        ),
    ],
    (LitterRobot4, LitterRobot5): [
        RobotSensorEntityDescription[LitterRobot4 | LitterRobot5](
            key="litter_level",
            translation_key="litter_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.litter_level,
        ),
        RobotSensorEntityDescription[LitterRobot4 | LitterRobot5](
            key="pet_weight",
            translation_key="pet_weight",
            native_unit_of_measurement=UnitOfMass.POUNDS,
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.pet_weight,
        ),
    ],
    LitterRobot5: [
        RobotSensorEntityDescription[LitterRobot5](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.wifi_rssi,
        ),
        RobotSensorEntityDescription[LitterRobot5](
            key="firmware",
            translation_key="firmware",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda robot: robot.firmware,
        ),
        RobotSensorEntityDescription[LitterRobot5](
            key="setup_date",
            translation_key="setup_date",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda robot: robot.setup_date,
        ),
        RobotSensorEntityDescription[LitterRobot5](
            key="scoops_saved_count",
            translation_key="scoops_saved_count",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda robot: robot.scoops_saved_count,
        ),
        RobotSensorEntityDescription[LitterRobot5](
            key="next_filter_replacement",
            translation_key="next_filter_replacement",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda robot: robot.next_filter_replacement_date,
        ),
    ],
    FeederRobot: [
        RobotSensorEntityDescription[FeederRobot](
            key="food_dispensed_today",
            translation_key="food_dispensed_today",
            state_class=SensorStateClass.TOTAL,
            last_reset_fn=dt_util.start_of_local_day,
            value_fn=(
                lambda robot: robot.get_food_dispensed_since(
                    dt_util.start_of_local_day()
                )
            ),
        ),
        RobotSensorEntityDescription[FeederRobot](
            key="food_level",
            translation_key="food_level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda robot: robot.food_level,
        ),
        RobotSensorEntityDescription[FeederRobot](
            key="last_feeding",
            translation_key="last_feeding",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=(
                lambda robot: (
                    robot.last_feeding["timestamp"] if robot.last_feeding else None
                )
            ),
        ),
        RobotSensorEntityDescription[FeederRobot](
            key="next_feeding",
            translation_key="next_feeding",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda robot: robot.next_feeding,
        ),
    ],
}

PET_SENSORS: list[RobotSensorEntityDescription] = [
    RobotSensorEntityDescription[Pet](
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pet: pet.weight,
    ),
    RobotSensorEntityDescription[Pet](
        key="visits_today",
        translation_key="visits_today",
        state_class=SensorStateClass.TOTAL,
        last_reset_fn=dt_util.start_of_local_day,
        value_fn=lambda pet: pet.get_visits_since(dt_util.start_of_local_day()),
    ),
    RobotSensorEntityDescription[Pet](
        key="visits_this_week",
        translation_key="visits_this_week",
        state_class=SensorStateClass.TOTAL,
        last_reset_fn=_start_of_local_week,
        value_fn=lambda pet: pet.get_visits_since(_start_of_local_week()),
    ),
]


CAMERA_EVENT_TYPES = [
    "pet_visit",
    "cat_detect",
    "motion",
    "cycle_completed",
    "cycle_interrupted",
    "litter_low",
    "offline",
]

ACTIVITY_TYPE_MAP: dict[str, str] = {
    "PET_VISIT": "pet_visit",
    "CAT_DETECT": "cat_detect",
    "MOTION": "motion",
    "CYCLE_COMPLETED": "cycle_completed",
    "CYCLE_INTERRUPTED": "cycle_interrupted",
    "LITTER_LOW": "litter_low",
    "OFFLINE": "offline",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        LitterRobotSensorEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, entity_descriptions in ROBOT_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    ]
    entities.extend(
        LitterRobotSensorEntity(
            robot=pet, coordinator=coordinator, description=description
        )
        for pet in coordinator.account.pets
        for description in PET_SENSORS
    )
    entities.extend(
        LitterRobotLastEventSensor(robot=robot, coordinator=coordinator)
        for robot in coordinator.account.robots
        if isinstance(robot, LitterRobot5) and robot.has_camera
    )
    entities.extend(
        LitterRobotPetLastVisitSensor(pet=pet, coordinator=coordinator)
        for pet in coordinator.account.pets
    )
    async_add_entities(entities)


class LitterRobotSensorEntity(LitterRobotEntity[_WhiskerEntityT], SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: RobotSensorEntityDescription[_WhiskerEntityT]

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        return self.entity_description.value_fn(self.robot)

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        return self.entity_description.last_reset_fn() or super().last_reset


EVENT_TYPE_LABELS: dict[str, str] = {
    "pet_visit": "Pet visit",
    "cat_detect": "Motion detected",
    "motion": "Motion",
    "cycle_completed": "Cycle completed",
    "cycle_interrupted": "Cycle interrupted",
    "litter_low": "Litter low",
    "offline": "Offline",
}


class LitterRobotLastEventSensor(LitterRobotEntity[LitterRobot5], SensorEntity):
    """Sensor showing the most recent camera event with pet name."""

    _attr_translation_key = "last_camera_event"

    def __init__(
        self,
        robot: LitterRobot5,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the last camera event sensor."""
        super().__init__(
            robot,
            coordinator,
            SensorEntityDescription(key="last_camera_event"),
        )

    @property
    def native_value(self) -> str | None:
        """Return a descriptive string for the most recent camera activity."""
        activities = self.coordinator.camera_activities.get(self.robot.serial, [])
        if not activities:
            return None
        latest = activities[0]
        raw_type = latest.get("type", "")
        event_type = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())
        label = EVENT_TYPE_LABELS.get(event_type, event_type)

        pet_ids = latest.get("petIds") or []
        if pet_ids:
            name_map = self.coordinator.pet_name_map
            pet_names = [name_map.get(pid, pid) for pid in pet_ids]
            pet_str = ", ".join(pet_names)
            return f"{pet_str} - {label}"

        return label

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for the latest activity."""
        activities = self.coordinator.camera_activities.get(self.robot.serial, [])
        if not activities:
            return None
        latest = activities[0]
        attrs: dict[str, Any] = {}
        raw_type = latest.get("type", "")
        attrs["event_type"] = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())
        pet_ids = latest.get("petIds") or []
        if pet_ids:
            name_map = self.coordinator.pet_name_map
            pet_names = [name_map.get(pid, pid) for pid in pet_ids]
            attrs["pet_name"] = pet_names[0] if len(pet_names) == 1 else pet_names
            attrs["pet_id"] = pet_ids[0] if len(pet_ids) == 1 else pet_ids
        if (waste_type := latest.get("wasteType")) is not None:
            attrs["waste_type"] = waste_type
        if (waste_weight := latest.get("wasteWeight")) is not None:
            attrs["waste_weight_oz"] = _waste_weight_oz(waste_weight)
        if (duration := latest.get("duration")) is not None:
            attrs["duration"] = _format_duration(duration)
        if (pet_weight := latest.get("petWeight")) is not None:
            attrs["pet_weight"] = round(pet_weight / 100, 1)
        if (timestamp := latest.get("timestamp")) is not None:
            attrs["timestamp"] = timestamp
        if (event_id := latest.get("eventId")) is not None:
            attrs["event_id"] = event_id

        # Recent activity history for dashboard rendering
        recording_map = self.coordinator.get_recording_map(self.robot.serial)
        attrs["recent_history"] = _build_activity_list(
            activities[:MAX_HISTORY_ENTRIES],
            self.coordinator.pet_name_map,
            recording_map,
        )
        attrs["is_reassigned"] = latest.get("isReassigned", False)
        return attrs or None


def _build_activity_list(
    activities: list[dict[str, Any]],
    pet_name_map: dict[str, str],
    recording_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build a list of activity dicts for dashboard rendering."""
    result: list[dict[str, Any]] = []
    for activity in activities:
        pet_ids = activity.get("petIds") or []
        pet_id = activity.get("petId") or (pet_ids[0] if pet_ids else None)
        pet_name = pet_name_map.get(pet_id, "Unknown") if pet_id else "Unknown"

        raw_type = activity.get("type", "")
        event_type = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())

        entry: dict[str, Any] = {
            "event_type": EVENT_TYPE_LABELS.get(event_type, event_type),
            "pet": pet_name,
            "timestamp": activity.get("timestamp", ""),
            "event_id": activity.get("eventId", ""),
            "is_reassigned": activity.get("isReassigned", False),
        }

        if (waste_type := activity.get("wasteType")) is not None:
            entry["waste_type"] = waste_type
        if (waste_weight := activity.get("wasteWeight")) is not None:
            entry["waste_oz"] = _waste_weight_oz(waste_weight)
        if (pet_weight := activity.get("petWeight")) is not None:
            entry["weight_lbs"] = round(pet_weight / 100, 1)
        if (duration := activity.get("duration")) is not None:
            entry["duration"] = _format_duration(duration)

        # Match to recording file if available
        if recording_map and activity.get("timestamp"):
            try:
                ts = datetime.fromisoformat(activity["timestamp"])
                prefix = ts.strftime("%Y%m%d_%H%M")
                for fname, url in recording_map.items():
                    if fname.startswith(prefix):
                        entry["recording_url"] = url
                        break
            except (ValueError, TypeError):
                pass

        result.append(entry)
    return result


def _waste_weight_oz(raw: float) -> float:
    """Convert raw wasteWeight to ounces (same scale as petWeight ÷100 for lbs)."""
    return round(raw / 100 * 16, 1)


def _format_duration(seconds: int) -> str:
    """Format seconds as 'Xm Ys' when >= 60, otherwise 'Xs'."""
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    return f"{seconds}s"


class LitterRobotPetLastVisitSensor(LitterRobotEntity[Pet], SensorEntity):
    """Sensor showing the most recent litter box visit for a specific pet."""

    _attr_translation_key = "last_visit"

    def __init__(
        self,
        pet: Pet,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the per-pet last visit sensor."""
        super().__init__(
            pet,
            coordinator,
            SensorEntityDescription(key="last_visit"),
        )
        self._pet_id = pet.id

    def _pet_activities(self) -> list[dict[str, Any]]:
        """Return all activities for this pet across all robots."""
        result: list[dict[str, Any]] = []
        for activities in self.coordinator.camera_activities.values():
            for activity in activities:
                pet_ids = activity.get("petIds") or []
                pet_id = activity.get("petId")
                if self._pet_id in pet_ids or self._pet_id == pet_id:
                    result.append(activity)
        return result

    def _today_activities(self) -> list[dict[str, Any]]:
        """Return today's activities for this pet."""
        start_of_day = dt_util.start_of_local_day()
        result: list[dict[str, Any]] = []
        for activity in self._pet_activities():
            ts = activity.get("timestamp")
            if not ts:
                continue
            try:
                activity_dt = datetime.fromisoformat(ts)
                if activity_dt >= start_of_day:
                    result.append(activity)
            except ValueError, TypeError:
                continue
        return result

    @property
    def native_value(self) -> str | None:
        """Return a descriptive string for the pet's most recent visit."""
        activities = self._pet_activities()
        if not activities:
            return None
        raw_type = activities[0].get("type", "")
        event_type = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())
        return EVENT_TYPE_LABELS.get(event_type, event_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return last visit details and daily aggregates."""
        activities = self._pet_activities()
        if not activities:
            return None
        latest = activities[0]
        attrs: dict[str, Any] = {}

        # Last visit details
        attrs["pet_id"] = self._pet_id
        raw_type = latest.get("type", "")
        attrs["event_type"] = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())
        if (event_id := latest.get("eventId")) is not None:
            attrs["event_id"] = event_id
        if (waste_type := latest.get("wasteType")) is not None:
            attrs["waste_type"] = waste_type
        if (waste_weight := latest.get("wasteWeight")) is not None:
            attrs["waste_weight_oz"] = _waste_weight_oz(waste_weight)
        if (duration := latest.get("duration")) is not None:
            attrs["duration"] = _format_duration(duration)
        if (pet_weight := latest.get("petWeight")) is not None:
            attrs["pet_weight"] = round(pet_weight / 100, 1)
        if (timestamp := latest.get("timestamp")) is not None:
            attrs["timestamp"] = timestamp
        attrs["is_reassigned"] = latest.get("isReassigned", False)

        # Daily aggregates
        today = self._today_activities()
        urine_count = 0
        urine_weight = 0.0
        feces_count = 0
        feces_weight = 0.0
        total_duration = 0
        for act in today:
            wt = (act.get("wasteType") or "").lower()
            ww = act.get("wasteWeight") or 0.0
            dur = act.get("duration") or 0
            total_duration += dur
            if wt == "urine":
                urine_count += 1
                urine_weight += ww
            elif wt == "feces":
                feces_count += 1
                feces_weight += ww

        attrs["urine_today"] = urine_count
        attrs["urine_weight_today_oz"] = _waste_weight_oz(urine_weight)
        attrs["feces_today"] = feces_count
        attrs["feces_weight_today_oz"] = _waste_weight_oz(feces_weight)
        attrs["total_duration_today"] = _format_duration(total_duration)

        # Recent visit history for dashboard rendering
        # Gather recording maps from all robots for URL matching
        combined_map: dict[str, str] = {}
        for serial in self.coordinator.camera_activities:
            combined_map.update(self.coordinator.get_recording_map(serial))
        attrs["recent_history"] = _build_activity_list(
            activities[:MAX_HISTORY_ENTRIES],
            self.coordinator.pet_name_map,
            combined_map,
        )

        return attrs
