"""Support for Habitica sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import logging
from typing import Any
from uuid import UUID

from habiticalib import ContentData, GroupData, HabiticaClass, TaskData, UserData, ha

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import HABITICA_KEY
from .const import ASSETS_URL, DATA_HABIT_SENSORS, DOMAIN
from .coordinator import HabiticaConfigEntry, HabiticaDataUpdateCoordinator
from .entity import HabiticaBase, HabiticaPartyBase, HabiticaPartyMemberBase
from .util import (
    collected_quest_items,
    get_attribute_points,
    get_attributes_total,
    inventory_list,
    pending_damage,
    pending_quest_items,
    quest_attributes,
    quest_boss,
    rage_attributes,
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

    value_fn: Callable[[UserData, ContentData], StateType | datetime]
    attributes_fn: Callable[[UserData, ContentData], dict[str, Any] | None] | None = (
        None
    )
    entity_picture: str | None = None


@dataclass(kw_only=True, frozen=True)
class HabiticaPartySensorEntityDescription(SensorEntityDescription):
    """Habitica Party Sensor Description."""

    value_fn: Callable[[GroupData, ContentData], StateType]
    entity_picture: Callable[[GroupData], str | None] | str | None = None
    attributes_fn: Callable[[GroupData, ContentData], dict[str, Any] | None] | None = (
        None
    )


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
    MEMBER_COUNT = "member_count"
    GROUP_LEADER = "group_leader"
    QUEST = "quest"
    BOSS = "boss"
    BOSS_HP = "boss_hp"
    BOSS_HP_REMAINING = "boss_hp_remaining"
    COLLECTED_ITEMS = "collected_items"
    BOSS_RAGE = "boss_rage"
    BOSS_RAGE_LIMIT = "boss_rage_limit"
    LAST_CHECKIN = "last_checkin"


SENSOR_DESCRIPTIONS_COMMON: tuple[HabiticaSensorEntityDescription, ...] = (
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.DISPLAY_NAME,
        translation_key=HabiticaSensorEntity.DISPLAY_NAME,
        value_fn=lambda user, _: user.profile.name,
        attributes_fn=lambda user, _: {
            "username": f"@{user.auth.local.username}",
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
        key=HabiticaSensorEntity.CLASS,
        translation_key=HabiticaSensorEntity.CLASS,
        value_fn=lambda user, _: user.stats.Class.value if user.stats.Class else None,
        device_class=SensorDeviceClass.ENUM,
        options=[item.value for item in HabiticaClass],
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
        key=HabiticaSensorEntity.LAST_CHECKIN,
        translation_key=HabiticaSensorEntity.LAST_CHECKIN,
        value_fn=(
            lambda user, _: dt_util.as_local(last)
            if (last := user.auth.timestamps.loggedin)
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)
SENSOR_DESCRIPTIONS: tuple[HabiticaSensorEntityDescription, ...] = (
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.GOLD,
        translation_key=HabiticaSensorEntity.GOLD,
        suggested_display_precision=2,
        value_fn=lambda user, _: user.stats.gp,
        entity_picture=ha.GP,
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
    HabiticaSensorEntityDescription(
        key=HabiticaSensorEntity.HABITS,
        translation_key=HabiticaSensorEntity.HABITS,
        value_fn=lambda user, _: len([h for h in user.tasksOrder.habits if h]),
    ),
)


SENSOR_DESCRIPTIONS_PARTY: tuple[HabiticaPartySensorEntityDescription, ...] = (
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.MEMBER_COUNT,
        translation_key=HabiticaSensorEntity.MEMBER_COUNT,
        value_fn=lambda party, _: party.memberCount,
        entity_picture=ha.PARTY,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.GROUP_LEADER,
        translation_key=HabiticaSensorEntity.GROUP_LEADER,
        value_fn=lambda party, _: party.leader.profile.name,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.QUEST,
        translation_key=HabiticaSensorEntity.QUEST,
        value_fn=lambda p, c: c.quests[p.quest.key].text if p.quest.key else None,
        attributes_fn=quest_attributes,
        entity_picture=(
            lambda party: f"inventory_quest_scroll_{party.quest.key}.png"
            if party.quest.key
            else None
        ),
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.BOSS,
        translation_key=HabiticaSensorEntity.BOSS,
        value_fn=lambda p, c: boss.name if (boss := quest_boss(p, c)) else None,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.BOSS_HP,
        translation_key=HabiticaSensorEntity.BOSS_HP,
        value_fn=lambda p, c: boss.hp if (boss := quest_boss(p, c)) else None,
        entity_picture=ha.HP,
        suggested_display_precision=0,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.BOSS_HP_REMAINING,
        translation_key=HabiticaSensorEntity.BOSS_HP_REMAINING,
        value_fn=lambda p, _: p.quest.progress.hp,
        entity_picture=ha.HP,
        suggested_display_precision=2,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.COLLECTED_ITEMS,
        translation_key=HabiticaSensorEntity.COLLECTED_ITEMS,
        value_fn=(
            lambda p, _: sum(n for n in p.quest.progress.collect.values())
            if p.quest.progress.collect
            else None
        ),
        attributes_fn=collected_quest_items,
        entity_picture=(
            lambda p: f"quest_{p.quest.key}_{k}.png"
            if p.quest.progress.collect
            and (k := next(iter(p.quest.progress.collect), None))
            else None
        ),
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.BOSS_RAGE,
        translation_key=HabiticaSensorEntity.BOSS_RAGE,
        value_fn=lambda p, _: p.quest.progress.rage,
        entity_picture=ha.RAGE,
        suggested_display_precision=2,
    ),
    HabiticaPartySensorEntityDescription(
        key=HabiticaSensorEntity.BOSS_RAGE_LIMIT,
        translation_key=HabiticaSensorEntity.BOSS_RAGE_LIMIT,
        value_fn=(
            lambda p, c: boss.rage.value
            if (boss := quest_boss(p, c)) and boss.rage
            else None
        ),
        entity_picture=ha.RAGE,
        suggested_display_precision=0,
        attributes_fn=rage_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica sensors."""

    coordinator = config_entry.runtime_data

    # Initialize habit sensor registry in hass.data
    config_entry_id = config_entry.entry_id
    if DATA_HABIT_SENSORS not in hass.data:
        hass.data[DATA_HABIT_SENSORS] = {}
    if config_entry_id not in hass.data[DATA_HABIT_SENSORS]:
        hass.data[DATA_HABIT_SENSORS][config_entry_id] = {}

    async_add_entities(
        HabiticaSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS + SENSOR_DESCRIPTIONS_COMMON
    )

    # Add individual habit sensors with dynamic management
    habits_added: set[str] = set()

    @callback
    def add_habit_sensors() -> None:
        """Add or remove habit sensors based on coordinator data."""
        nonlocal habits_added
        sensors = []
        entity_registry = er.async_get(hass)

        current_habits = set()
        if coordinator.data and coordinator.data.habits:
            for habit in coordinator.data.habits:
                if habit and habit.id:
                    habit_id = str(habit.id)
                    current_habits.add(habit_id)

                    # Add new habit sensor if not already added
                    if habit_id not in habits_added:
                        sensors.append(HabiticaHabitSensor(coordinator, habit))
                        habits_added.add(habit_id)

        # Remove sensors for habits that no longer exist
        for habit_id in habits_added.copy():
            if habit_id not in current_habits:
                if entity_id := entity_registry.async_get_entity_id(
                    SENSOR_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_habit_{habit_id}",
                ):
                    entity_registry.async_remove(entity_id)
                habits_added.remove(habit_id)

        if sensors:
            async_add_entities(sensors)

    coordinator.async_add_listener(add_habit_sensors)
    add_habit_sensors()

    if party := coordinator.data.user.party.id:
        party_coordinator = hass.data[HABITICA_KEY][party]
        async_add_entities(
            HabiticaPartySensor(
                party_coordinator,
                config_entry,
                description,
                coordinator.content,
            )
            for description in SENSOR_DESCRIPTIONS_PARTY
        )
        for subentry_id, subentry in config_entry.subentries.items():
            if (
                subentry.unique_id
                and UUID(subentry.unique_id) in party_coordinator.data.members
            ):
                async_add_entities(
                    [
                        HabiticaPartyMemberSensor(
                            coordinator,
                            party_coordinator,
                            description,
                            subentry,
                        )
                        for description in SENSOR_DESCRIPTIONS_COMMON
                    ],
                    config_subentry_id=subentry_id,
                )


class HabiticaSensor(HabiticaBase, SensorEntity):
    """A generic Habitica sensor."""

    entity_description: HabiticaSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the device."""

        return (
            self.entity_description.value_fn(self.user, self.coordinator.content)
            if self.user is not None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, float | None] | None:
        """Return entity specific state attributes."""
        if self.user is not None and (func := self.entity_description.attributes_fn):
            return func(self.user, self.coordinator.content)
        return None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if (
            self.entity_description.key is HabiticaSensorEntity.CLASS
            and self.user is not None
            and (_class := self.user.stats.Class)
        ):
            return SVG_CLASS[_class]

        if (
            self.entity_description.key is HabiticaSensorEntity.DISPLAY_NAME
            and self.user is not None
            and (img_url := self.user.profile.imageUrl)
        ):
            return img_url

        if entity_picture := self.entity_description.entity_picture:
            return (
                entity_picture
                if entity_picture.startswith("data:image")
                else f"{ASSETS_URL}{entity_picture}"
            )

        return None


class HabiticaHabitSensor(
    CoordinatorEntity[HabiticaDataUpdateCoordinator], SensorEntity
):
    """Sensor for individual Habitica habits."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        habit: TaskData,
    ) -> None:
        """Initialize the habit sensor."""
        super().__init__(coordinator)
        self.habit = habit
        self.habit_id = str(habit.id)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_habit_{habit.id}"
        self._attr_name = habit.text
        self._optimistic_value: float | None = None
        self._optimistic_counter_up: int | None = None
        self._optimistic_counter_down: int | None = None

        # Set device info to link to the main Habitica device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )

    def _get_current_habit(self) -> TaskData | None:
        """Get current habit data from coordinator."""
        if self.coordinator.data and self.coordinator.data.habits:
            for habit in self.coordinator.data.habits:
                if habit and habit.id == self.habit.id:
                    return habit
        return None

    def set_optimistic_update(self, value_delta: float, direction: str) -> None:
        """Set optimistic value for immediate UI feedback."""
        current_habit = self._get_current_habit()
        if current_habit:
            # Set optimistic value
            current_value = current_habit.value if current_habit.value else 0
            self._optimistic_value = round(current_value + value_delta, 2)

            # Set optimistic counters
            if direction == "up":
                self._optimistic_counter_up = (current_habit.counterUp or 0) + 1
                self._optimistic_counter_down = current_habit.counterDown or 0
            else:
                self._optimistic_counter_up = current_habit.counterUp or 0
                self._optimistic_counter_down = (current_habit.counterDown or 0) + 1

            # Trigger state update
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Register this sensor in hass.data for button lookup
        config_entry_id = self.coordinator.config_entry.entry_id
        if DATA_HABIT_SENSORS in self.hass.data:
            if config_entry_id in self.hass.data[DATA_HABIT_SENSORS]:
                self.hass.data[DATA_HABIT_SENSORS][config_entry_id][self.habit_id] = (
                    self
                )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        # Unregister this sensor
        config_entry_id = self.coordinator.config_entry.entry_id
        if (
            DATA_HABIT_SENSORS in self.hass.data
            and config_entry_id in self.hass.data[DATA_HABIT_SENSORS]
            and self.habit_id in self.hass.data[DATA_HABIT_SENSORS][config_entry_id]
        ):
            del self.hass.data[DATA_HABIT_SENSORS][config_entry_id][self.habit_id]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic values when real data arrives
        self._optimistic_value = None
        self._optimistic_counter_up = None
        self._optimistic_counter_down = None
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType:
        """Return the habit value."""
        # Return optimistic value if set (for immediate UI feedback)
        if self._optimistic_value is not None:
            return self._optimistic_value

        # Find the current habit data from coordinator
        current_habit = self._get_current_habit()
        if current_habit:
            return round(current_habit.value, 2) if current_habit.value else 0
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return habit specific attributes."""
        current_habit = self._get_current_habit()
        if current_habit:
            # Use optimistic counters if available for immediate UI feedback
            counter_up = (
                self._optimistic_counter_up
                if self._optimistic_counter_up is not None
                else (current_habit.counterUp or 0)
            )
            counter_down = (
                self._optimistic_counter_down
                if self._optimistic_counter_down is not None
                else (current_habit.counterDown or 0)
            )

            return {
                "habit_id": str(current_habit.id),
                "text": current_habit.text,
                "notes": current_habit.notes or "",
                "counter_up": counter_up,
                "counter_down": counter_down,
                "frequency": current_habit.frequency.value
                if current_habit.frequency
                else "daily",
                "up": current_habit.up if hasattr(current_habit, "up") else True,
                "down": current_habit.down if hasattr(current_habit, "down") else True,
            }
        return {}


class HabiticaPartyMemberSensor(HabiticaSensor, HabiticaPartyMemberBase):
    """Habitica party member sensor."""


class HabiticaPartySensor(HabiticaPartyBase, SensorEntity):
    """Habitica party sensor."""

    entity_description: HabiticaPartySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the device."""

        return self.entity_description.value_fn(
            self.coordinator.data.party, self.content
        )

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        pic = self.entity_description.entity_picture

        entity_picture = (
            pic
            if isinstance(pic, str) or pic is None
            else pic(self.coordinator.data.party)
        )

        return (
            None
            if not entity_picture
            else entity_picture
            if entity_picture.startswith("data:image")
            else f"{ASSETS_URL}{entity_picture}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        if func := self.entity_description.attributes_fn:
            return func(self.coordinator.data.party, self.content)
        return None
