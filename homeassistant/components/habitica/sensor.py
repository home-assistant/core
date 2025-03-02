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
    ha,
)

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import ASSETS_URL, DOMAIN
from .coordinator import HabiticaConfigEntry, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase
from .util import get_attribute_points, get_attributes_total, inventory_list

_LOGGER = logging.getLogger(__name__)

SVG_CLASS = {
    HabiticaClass.WARRIOR: ha.WARRIOR,
    HabiticaClass.ROGUE: ha.ROGUE,
    HabiticaClass.MAGE: ha.WIZARD,
    HabiticaClass.HEALER: ha.HEALER,
}


PARALLEL_UPDATES = 1


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
    EGGS_TOTAL = "eggs_total"
    HATCHING_POTIONS_TOTAL = "hatching_potions_total"
    FOOD_TOTAL = "food_total"
    SADDLE = "saddle"
    QUEST_SCROLLS = "quest_scrolls"


SENSOR_DESCRIPTIONS: tuple[HabiticaSensorEntityDescription, ...] = (
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.DISPLAY_NAME,
        translation_key=HabiticaSensorEntity.DISPLAY_NAME,
        value_fn=lambda user, _: user.profile.name,
        attributes_fn=lambda user, _: {
            "blurb": user.profile.blurb,
            "joined": (
                dt_util.as_local(joined).date()
                if (joined := user.auth.timestamps.created)
                else None
            ),
            "last_login": (
                dt_util.as_local(last).date()
                if (last := user.auth.timestamps.loggedin)
                else None
            ),
            "total_logins": user.loginIncentives,
        },
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.HEALTH,
        translation_key=HabiticaSensorEntity.HEALTH,
        suggested_display_precision=0,
        value_fn=lambda user, _: user.stats.hp,
        entity_picture=ha.HP,
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
        entity_picture=ha.MP,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.MANA_MAX,
        translation_key=HabiticaSensorEntity.MANA_MAX,
        value_fn=lambda user, _: user.stats.maxMP,
        entity_picture=ha.MP,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.EXPERIENCE,
        translation_key=HabiticaSensorEntity.EXPERIENCE,
        value_fn=lambda user, _: user.stats.exp,
        entity_picture=ha.XP,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.EXPERIENCE_MAX,
        translation_key=HabiticaSensorEntity.EXPERIENCE_MAX,
        value_fn=lambda user, _: user.stats.toNextLevel,
        entity_picture=ha.XP,
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
        entity_picture=ha.GP,
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
        value_fn=lambda user, _: None if (b := user.balance) is None else round(b * 4),
        suggested_display_precision=0,
        entity_picture="shop_gem.png",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.TRINKETS,
        translation_key=HabiticaSensorEntity.TRINKETS,
        value_fn=lambda user, _: user.purchased.plan.consecutive.trinkets,
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
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.EGGS_TOTAL,
        translation_key=HabiticaSensorEntity.EGGS_TOTAL,
        value_fn=lambda user, _: sum(n for n in user.items.eggs.values()),
        entity_picture="Pet_Egg_Egg.png",
        attributes_fn=lambda user, content: inventory_list(user, content, "eggs"),
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.HATCHING_POTIONS_TOTAL,
        translation_key=HabiticaSensorEntity.HATCHING_POTIONS_TOTAL,
        value_fn=lambda user, _: sum(n for n in user.items.hatchingPotions.values()),
        entity_picture="Pet_HatchingPotion_RoyalPurple.png",
        attributes_fn=(
            lambda user, content: inventory_list(user, content, "hatchingPotions")
        ),
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.FOOD_TOTAL,
        translation_key=HabiticaSensorEntity.FOOD_TOTAL,
        value_fn=(
            lambda user, _: sum(n for k, n in user.items.food.items() if k != "Saddle")
        ),
        entity_picture=ha.FOOD,
        attributes_fn=lambda user, content: inventory_list(user, content, "food"),
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.SADDLE,
        translation_key=HabiticaSensorEntity.SADDLE,
        value_fn=lambda user, _: user.items.food.get("Saddle", 0),
        entity_picture="Pet_Food_Saddle.png",
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.QUEST_SCROLLS,
        translation_key=HabiticaSensorEntity.QUEST_SCROLLS,
        value_fn=(lambda user, _: sum(n for n in user.items.quests.values())),
        entity_picture="inventory_quest_scroll_dustbunnies.png",
        attributes_fn=lambda user, content: inventory_list(user, content, "quests"),
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


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    coordinator = config_entry.runtime_data
    ent_reg = er.async_get(hass)
    entities: list[SensorEntity] = []
    description: SensorEntityDescription

    def add_deprecated_entity(
        description: SensorEntityDescription,
        entity_cls: Callable[
            [HabiticaDataUpdateCoordinator, SensorEntityDescription], SensorEntity
        ],
    ) -> None:
        """Add deprecated entities."""
        if entity_id := ent_reg.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{config_entry.unique_id}_{description.key}",
        ):
            entity_entry = ent_reg.async_get(entity_id)
            if entity_entry and entity_entry.disabled:
                ent_reg.async_remove(entity_id)
                async_delete_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{description.key}",
                )
            elif entity_entry:
                entities.append(entity_cls(coordinator, description))
                if entity_used_in(hass, entity_id):
                    async_create_issue(
                        hass,
                        DOMAIN,
                        f"deprecated_entity_{description.key}",
                        breaks_in_ha_version="2025.8.0",
                        is_fixable=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="deprecated_entity",
                        translation_placeholders={
                            "name": str(
                                entity_entry.name or entity_entry.original_name
                            ),
                            "entity": entity_id,
                        },
                    )

    for description in SENSOR_DESCRIPTIONS:
        if description.key is HabiticaSensorEntity.HEALTH_MAX:
            add_deprecated_entity(description, HabiticaSensor)
        else:
            entities.append(HabiticaSensor(coordinator, description))

    for description in TASK_SENSOR_DESCRIPTION:
        add_deprecated_entity(description, HabiticaTaskSensor)

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
        if self.entity_description.key is HabiticaSensorEntity.CLASS and (
            _class := self.coordinator.data.user.stats.Class
        ):
            return SVG_CLASS[_class]

        if self.entity_description.key is HabiticaSensorEntity.DISPLAY_NAME and (
            img_url := self.coordinator.data.user.profile.imageUrl
        ):
            return img_url

        if entity_picture := self.entity_description.entity_picture:
            return (
                entity_picture
                if entity_picture.startswith("data:image")
                else f"{ASSETS_URL}{entity_picture}"
            )

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
