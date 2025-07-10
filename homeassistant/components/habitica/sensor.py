"""Support for Habitica sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from habiticalib import ContentData, HabiticaClass, TaskData, UserData, ha

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import ASSETS_URL
from .coordinator import HabiticaConfigEntry
from .entity import HabiticaBase
from .util import (
    get_attribute_points,
    get_attributes_total,
    inventory_list,
    pending_damage,
    pending_quest_items,
)

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
    PENDING_DAMAGE = "pending_damage"
    PENDING_QUEST_ITEMS = "pending_quest_items"


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
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.PENDING_DAMAGE,
        translation_key=HabiticaSensorEntity.PENDING_DAMAGE,
        value_fn=pending_damage,
        suggested_display_precision=1,
        entity_picture=ha.DAMAGE,
    ),
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.PENDING_QUEST_ITEMS,
        translation_key=HabiticaSensorEntity.PENDING_QUEST_ITEMS,
        value_fn=pending_quest_items,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        HabiticaSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


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
