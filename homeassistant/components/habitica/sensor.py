"""Support for Habitica sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
import logging
from typing import Any

from habiticalib import (
    ContentData,
    HabiticaClass,
    TaskData,
    TaskType,
    UserData,
    deserialize_task,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ASSETS_URL
from .entity import HabiticaBase
from .types import HabiticaConfigEntry
from .util import get_attribute_points, get_attributes_total

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class HabiticaSensorEntityDescription(SensorEntityDescription):
    """Habitica Sensor Description."""

    value_fn: Callable[[UserData, ContentData], StateType]
    attributes_fn: Callable[[UserData, ContentData], dict[str, Any] | None] | None = (
        None
    )
    entity_picture: str | None = None


@dataclass(kw_only=True, frozen=True)
class HabiticaTaskSensorEntityDescription(SensorEntityDescription):
    """Habitica Task Sensor Description."""

    value_fn: Callable[[list[TaskData]], list[TaskData]]


class HabiticaSensorEntity(StrEnum):
    """Habitica Entities."""

    DISPLAY_NAME = "display_name"
    HEALTH = "health"
    HEALTH_MAX = "health_max"
    MANA = "mana"
    MANA_MAX = "mana_max"
    EXPERIENCE = "experience"
    EXPERIENCE_MAX = "experience_max"
    LEVEL = "level"
    GOLD = "gold"
    CLASS = "class"
    HABITS = "habits"
    REWARDS = "rewards"
    GEMS = "gems"
    TRINKETS = "trinkets"
    STRENGTH = "strength"
    INTELLIGENCE = "intelligence"
    CONSTITUTION = "constitution"
    PERCEPTION = "perception"


SENSOR_DESCRIPTIONS: tuple[HabiticaSensorEntityDescription, ...] = (
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.DISPLAY_NAME,
        translation_key=HabiticaSensorEntity.DISPLAY_NAME,
        value_fn=lambda user, _: user.profile.name,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.HEALTH,
        translation_key=HabiticaSensorEntity.HEALTH,
        suggested_display_precision=0,
        value_fn=lambda user, _: user.stats.hp,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.HEALTH_MAX,
        translation_key=HabiticaSensorEntity.HEALTH_MAX,
        entity_registry_enabled_default=False,
        value_fn=lambda user, _: 50,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.MANA,
        translation_key=HabiticaSensorEntity.MANA,
        suggested_display_precision=0,
        value_fn=lambda user, _: user.stats.mp,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.MANA_MAX,
        translation_key=HabiticaSensorEntity.MANA_MAX,
        value_fn=lambda user, _: user.stats.maxMP,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.EXPERIENCE,
        translation_key=HabiticaSensorEntity.EXPERIENCE,
        value_fn=lambda user, _: user.stats.exp,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.EXPERIENCE_MAX,
        translation_key=HabiticaSensorEntity.EXPERIENCE_MAX,
        value_fn=lambda user, _: user.stats.toNextLevel,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.LEVEL,
        translation_key=HabiticaSensorEntity.LEVEL,
        value_fn=lambda user, _: user.stats.lvl,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.GOLD,
        translation_key=HabiticaSensorEntity.GOLD,
        suggested_display_precision=2,
        value_fn=lambda user, _: user.stats.gp,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.CLASS,
        translation_key=HabiticaSensorEntity.CLASS,
        value_fn=lambda user, _: user.stats.Class.value if user.stats.Class else None,
        device_class=SensorDeviceClass.ENUM,
        options=[item.value for item in HabiticaClass],
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.GEMS,
        translation_key=HabiticaSensorEntity.GEMS,
        value_fn=lambda user, _: round(user.balance * 4) if user.balance else None,
        suggested_display_precision=0,
        entity_picture="shop_gem.png",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.TRINKETS,
        translation_key=HabiticaSensorEntity.TRINKETS,
        value_fn=lambda user, _: user.purchased.plan.consecutive.trinkets or 0,
        suggested_display_precision=0,
        native_unit_of_measurement="⧖",
        entity_picture="notif_subscriber_reward.png",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.STRENGTH,
        translation_key=HabiticaSensorEntity.STRENGTH,
        value_fn=lambda user, content: get_attributes_total(user, content, "Str"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "Str"),
        suggested_display_precision=0,
        native_unit_of_measurement="STR",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.INTELLIGENCE,
        translation_key=HabiticaSensorEntity.INTELLIGENCE,
        value_fn=lambda user, content: get_attributes_total(user, content, "Int"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "Int"),
        suggested_display_precision=0,
        native_unit_of_measurement="INT",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.PERCEPTION,
        translation_key=HabiticaSensorEntity.PERCEPTION,
        value_fn=lambda user, content: get_attributes_total(user, content, "per"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "per"),
        suggested_display_precision=0,
        native_unit_of_measurement="PER",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.CONSTITUTION,
        translation_key=HabiticaSensorEntity.CONSTITUTION,
        value_fn=lambda user, content: get_attributes_total(user, content, "con"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "con"),
        suggested_display_precision=0,
        native_unit_of_measurement="CON",
    ),
)


TASKS_MAP_ID = "id"
TASKS_MAP = {
    "repeat": "repeat",
    "challenge": "challenge",
    "group": "group",
    "frequency": "frequency",
    "every_x": "everyX",
    "streak": "streak",
    "up": "up",
    "down": "down",
    "counter_up": "counterUp",
    "counter_down": "counterDown",
    "next_due": "nextDue",
    "yester_daily": "yesterDaily",
    "completed": "completed",
    "collapse_checklist": "collapseChecklist",
    "type": "Type",
    "notes": "notes",
    "tags": "tags",
    "value": "value",
    "priority": "priority",
    "start_date": "startDate",
    "days_of_month": "daysOfMonth",
    "weeks_of_month": "weeksOfMonth",
    "created_at": "createdAt",
    "text": "text",
    "is_due": "isDue",
}


TASK_SENSOR_DESCRIPTION: tuple[HabiticaTaskSensorEntityDescription, ...] = (
    HabiticaTaskSensorEntityDescription(
        key=HabiticaSensorEntity.HABITS,
        translation_key=HabiticaSensorEntity.HABITS,
        value_fn=lambda tasks: [r for r in tasks if r.Type is TaskType.HABIT],
    ),
    HabiticaTaskSensorEntityDescription(
        key=HabiticaSensorEntity.REWARDS,
        translation_key=HabiticaSensorEntity.REWARDS,
        value_fn=lambda tasks: [r for r in tasks if r.Type is TaskType.REWARD],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    coordinator = config_entry.runtime_data

    entities: list[SensorEntity] = [
        HabiticaSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        HabiticaTaskSensor(coordinator, description)
        for description in TASK_SENSOR_DESCRIPTION
    )
    async_add_entities(entities, True)


class HabiticaSensor(HabiticaBase, SensorEntity):
    """A generic Habitica sensor."""

    entity_description: HabiticaSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        return self.entity_description.value_fn(
            self.coordinator.data.user, self.coordinator.content
        )

    @property
    def extra_state_attributes(self) -> dict[str, float | None] | None:
        """Return entity specific state attributes."""
        if func := self.entity_description.attributes_fn:
            return func(self.coordinator.data.user, self.coordinator.content)
        return None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if entity_picture := self.entity_description.entity_picture:
            return f"{ASSETS_URL}{entity_picture}"
        return None


class HabiticaTaskSensor(HabiticaBase, SensorEntity):
    """A Habitica task sensor."""

    entity_description: HabiticaTaskSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        return len(self.entity_description.value_fn(self.coordinator.data.tasks))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of all user tasks."""
        attrs = {}

        # Map tasks to TASKS_MAP
        for task_data in self.entity_description.value_fn(self.coordinator.data.tasks):
            received_task = deserialize_task(asdict(task_data))
            task_id = received_task[TASKS_MAP_ID]
            task = {}
            for map_key, map_value in TASKS_MAP.items():
                if value := received_task.get(map_value):
                    task[map_key] = value
            attrs[str(task_id)] = task
        return attrs
