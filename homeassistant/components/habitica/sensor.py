"""Support for Habitica sensors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import StateType

from .const import ASSETS_URL, DOMAIN
from .entity import HabiticaBase
from .types import HabiticaConfigEntry
from .util import entity_used_in, get_attribute_points, get_attributes_total

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class HabitipySensorEntityDescription(SensorEntityDescription):
    """Habitipy Sensor Description."""

    value_fn: Callable[[dict[str, Any], dict[str, Any]], StateType]
    attributes_fn: (
        Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None] | None
    ) = None
    entity_picture: str | None = None


@dataclass(kw_only=True, frozen=True)
class HabitipyTaskSensorEntityDescription(SensorEntityDescription):
    """Habitipy Task Sensor Description."""

    value_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


class HabitipySensorEntity(StrEnum):
    """Habitipy Entities."""

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
    DAILIES = "dailys"
    TODOS = "todos"
    REWARDS = "rewards"
    GEMS = "gems"
    TRINKETS = "trinkets"
    STRENGTH = "strength"
    INTELLIGENCE = "intelligence"
    CONSTITUTION = "constitution"
    PERCEPTION = "perception"


SENSOR_DESCRIPTIONS: tuple[HabitipySensorEntityDescription, ...] = (
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.DISPLAY_NAME,
        translation_key=HabitipySensorEntity.DISPLAY_NAME,
        value_fn=lambda user, _: user.get("profile", {}).get("name"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.HEALTH,
        translation_key=HabitipySensorEntity.HEALTH,
        suggested_display_precision=0,
        value_fn=lambda user, _: user.get("stats", {}).get("hp"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.HEALTH_MAX,
        translation_key=HabitipySensorEntity.HEALTH_MAX,
        entity_registry_enabled_default=False,
        value_fn=lambda user, _: user.get("stats", {}).get("maxHealth"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.MANA,
        translation_key=HabitipySensorEntity.MANA,
        suggested_display_precision=0,
        value_fn=lambda user, _: user.get("stats", {}).get("mp"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.MANA_MAX,
        translation_key=HabitipySensorEntity.MANA_MAX,
        value_fn=lambda user, _: user.get("stats", {}).get("maxMP"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.EXPERIENCE,
        translation_key=HabitipySensorEntity.EXPERIENCE,
        value_fn=lambda user, _: user.get("stats", {}).get("exp"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.EXPERIENCE_MAX,
        translation_key=HabitipySensorEntity.EXPERIENCE_MAX,
        value_fn=lambda user, _: user.get("stats", {}).get("toNextLevel"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.LEVEL,
        translation_key=HabitipySensorEntity.LEVEL,
        value_fn=lambda user, _: user.get("stats", {}).get("lvl"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.GOLD,
        translation_key=HabitipySensorEntity.GOLD,
        suggested_display_precision=2,
        value_fn=lambda user, _: user.get("stats", {}).get("gp"),
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.CLASS,
        translation_key=HabitipySensorEntity.CLASS,
        value_fn=lambda user, _: user.get("stats", {}).get("class"),
        device_class=SensorDeviceClass.ENUM,
        options=["warrior", "healer", "wizard", "rogue"],
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.GEMS,
        translation_key=HabitipySensorEntity.GEMS,
        value_fn=lambda user, _: user.get("balance", 0) * 4,
        suggested_display_precision=0,
        entity_picture="shop_gem.png",
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.TRINKETS,
        translation_key=HabitipySensorEntity.TRINKETS,
        value_fn=(
            lambda user, _: user.get("purchased", {})
            .get("plan", {})
            .get("consecutive", {})
            .get("trinkets", 0)
        ),
        suggested_display_precision=0,
        native_unit_of_measurement="⧖",
        entity_picture="notif_subscriber_reward.png",
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.STRENGTH,
        translation_key=HabitipySensorEntity.STRENGTH,
        value_fn=lambda user, content: get_attributes_total(user, content, "str"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "str"),
        suggested_display_precision=0,
        native_unit_of_measurement="STR",
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.INTELLIGENCE,
        translation_key=HabitipySensorEntity.INTELLIGENCE,
        value_fn=lambda user, content: get_attributes_total(user, content, "int"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "int"),
        suggested_display_precision=0,
        native_unit_of_measurement="INT",
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.PERCEPTION,
        translation_key=HabitipySensorEntity.PERCEPTION,
        value_fn=lambda user, content: get_attributes_total(user, content, "per"),
        attributes_fn=lambda user, content: get_attribute_points(user, content, "per"),
        suggested_display_precision=0,
        native_unit_of_measurement="PER",
    ),
    HabitipySensorEntityDescription(
        key=HabitipySensorEntity.CONSTITUTION,
        translation_key=HabitipySensorEntity.CONSTITUTION,
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
    "type": "type",
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


TASK_SENSOR_DESCRIPTION: tuple[HabitipyTaskSensorEntityDescription, ...] = (
    HabitipyTaskSensorEntityDescription(
        key=HabitipySensorEntity.HABITS,
        translation_key=HabitipySensorEntity.HABITS,
        value_fn=lambda tasks: [r for r in tasks if r.get("type") == "habit"],
    ),
    HabitipyTaskSensorEntityDescription(
        key=HabitipySensorEntity.DAILIES,
        translation_key=HabitipySensorEntity.DAILIES,
        value_fn=lambda tasks: [r for r in tasks if r.get("type") == "daily"],
        entity_registry_enabled_default=False,
    ),
    HabitipyTaskSensorEntityDescription(
        key=HabitipySensorEntity.TODOS,
        translation_key=HabitipySensorEntity.TODOS,
        value_fn=lambda tasks: [
            r for r in tasks if r.get("type") == "todo" and not r.get("completed")
        ],
        entity_registry_enabled_default=False,
    ),
    HabitipyTaskSensorEntityDescription(
        key=HabitipySensorEntity.REWARDS,
        translation_key=HabitipySensorEntity.REWARDS,
        value_fn=lambda tasks: [r for r in tasks if r.get("type") == "reward"],
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
        HabitipySensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        HabitipyTaskSensor(coordinator, description)
        for description in TASK_SENSOR_DESCRIPTION
    )
    async_add_entities(entities, True)


class HabitipySensor(HabiticaBase, SensorEntity):
    """A generic Habitica sensor."""

    entity_description: HabitipySensorEntityDescription

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


class HabitipyTaskSensor(HabiticaBase, SensorEntity):
    """A Habitica task sensor."""

    entity_description: HabitipyTaskSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        return len(self.entity_description.value_fn(self.coordinator.data.tasks))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of all user tasks."""
        attrs = {}

        # Map tasks to TASKS_MAP
        for received_task in self.entity_description.value_fn(
            self.coordinator.data.tasks
        ):
            task_id = received_task[TASKS_MAP_ID]
            task = {}
            for map_key, map_value in TASKS_MAP.items():
                if value := received_task.get(map_value):
                    task[map_key] = value
            attrs[task_id] = task
        return attrs

    async def async_added_to_hass(self) -> None:
        """Raise issue when entity is registered and was not disabled."""
        if TYPE_CHECKING:
            assert self.unique_id
        if entity_id := er.async_get(self.hass).async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, self.unique_id
        ):
            if (
                self.enabled
                and self.entity_description.key
                in (HabitipySensorEntity.TODOS, HabitipySensorEntity.DAILIES)
                and entity_used_in(self.hass, entity_id)
            ):
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self.entity_description.key}",
                    breaks_in_ha_version="2025.2.0",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_task_entity",
                    translation_placeholders={
                        "task_name": str(self.name),
                        "entity": entity_id,
                    },
                )
            else:
                async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_task_entity_{self.entity_description.key}",
                )
        await super().async_added_to_hass()
