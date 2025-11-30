"""Habitica button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from habiticalib import Direction, Habitica, HabiticaClass, Skill, TaskType

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ASSETS_URL, DATA_HABIT_SENSORS, DOMAIN, OPTIMISTIC_HABIT_SCORE_DELTA
from .coordinator import (
    HabiticaConfigEntry,
    HabiticaData,
    HabiticaDataUpdateCoordinator,
)
from .entity import HabiticaBase

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HabiticaButtonEntityDescription(ButtonEntityDescription):
    """Describes Habitica button entity."""

    press_fn: Callable[[Habitica], Any]
    available_fn: Callable[[HabiticaData], bool]
    class_needed: HabiticaClass | None = None
    entity_picture: str | None = None


class HabiticaButtonEntity(StrEnum):
    """Habitica button entities."""

    RUN_CRON = "run_cron"
    BUY_HEALTH_POTION = "buy_health_potion"
    ALLOCATE_ALL_STAT_POINTS = "allocate_all_stat_points"
    REVIVE = "revive"
    MPHEAL = "mpheal"
    EARTH = "earth"
    FROST = "frost"
    DEFENSIVE_STANCE = "defensive_stance"
    VALOROUS_PRESENCE = "valorous_presence"
    INTIMIDATE = "intimidate"
    TOOLS_OF_TRADE = "tools_of_trade"
    STEALTH = "stealth"
    HEAL = "heal"
    PROTECT_AURA = "protect_aura"
    BRIGHTNESS = "brightness"
    HEAL_ALL = "heal_all"


BUTTON_DESCRIPTIONS: tuple[HabiticaButtonEntityDescription, ...] = (
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.RUN_CRON,
        translation_key=HabiticaButtonEntity.RUN_CRON,
        press_fn=lambda habitica: habitica.run_cron(),
        available_fn=lambda data: data.user.needsCron is True,
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.BUY_HEALTH_POTION,
        translation_key=HabiticaButtonEntity.BUY_HEALTH_POTION,
        press_fn=lambda habitica: habitica.buy_health_potion(),
        available_fn=(
            lambda data: (data.user.stats.gp or 0) >= 25
            and (data.user.stats.hp or 0) < 50
        ),
        entity_picture="shop_potion.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.ALLOCATE_ALL_STAT_POINTS,
        translation_key=HabiticaButtonEntity.ALLOCATE_ALL_STAT_POINTS,
        press_fn=lambda habitica: habitica.allocate_stat_points(),
        available_fn=(
            lambda data: data.user.preferences.automaticAllocation is True
            and (data.user.stats.points or 0) > 0
        ),
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.REVIVE,
        translation_key=HabiticaButtonEntity.REVIVE,
        press_fn=lambda habitica: habitica.revive(),
        available_fn=lambda data: data.user.stats.hp == 0,
    ),
)


CLASS_SKILLS: tuple[HabiticaButtonEntityDescription, ...] = (
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.MPHEAL,
        translation_key=HabiticaButtonEntity.MPHEAL,
        press_fn=lambda habitica: habitica.cast_skill(Skill.ETHEREAL_SURGE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 12
            and (data.user.stats.mp or 0) >= 30
        ),
        class_needed=HabiticaClass.MAGE,
        entity_picture="shop_mpheal.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.EARTH,
        translation_key=HabiticaButtonEntity.EARTH,
        press_fn=lambda habitica: habitica.cast_skill(Skill.EARTHQUAKE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 13
            and (data.user.stats.mp or 0) >= 35
        ),
        class_needed=HabiticaClass.MAGE,
        entity_picture="shop_earth.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.FROST,
        translation_key=HabiticaButtonEntity.FROST,
        press_fn=lambda habitica: habitica.cast_skill(Skill.CHILLING_FROST),
        # chilling frost can only be cast once per day (streaks buff is false)
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 14
            and (data.user.stats.mp or 0) >= 40
            and not data.user.stats.buffs.streaks
        ),
        class_needed=HabiticaClass.MAGE,
        entity_picture="shop_frost.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.DEFENSIVE_STANCE,
        translation_key=HabiticaButtonEntity.DEFENSIVE_STANCE,
        press_fn=lambda habitica: habitica.cast_skill(Skill.DEFENSIVE_STANCE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 12
            and (data.user.stats.mp or 0) >= 25
        ),
        class_needed=HabiticaClass.WARRIOR,
        entity_picture="shop_defensiveStance.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.VALOROUS_PRESENCE,
        translation_key=HabiticaButtonEntity.VALOROUS_PRESENCE,
        press_fn=lambda habitica: habitica.cast_skill(Skill.VALOROUS_PRESENCE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 13
            and (data.user.stats.mp or 0) >= 20
        ),
        class_needed=HabiticaClass.WARRIOR,
        entity_picture="shop_valorousPresence.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.INTIMIDATE,
        translation_key=HabiticaButtonEntity.INTIMIDATE,
        press_fn=lambda habitica: habitica.cast_skill(Skill.INTIMIDATING_GAZE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 14
            and (data.user.stats.mp or 0) >= 15
        ),
        class_needed=HabiticaClass.WARRIOR,
        entity_picture="shop_intimidate.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.TOOLS_OF_TRADE,
        translation_key=HabiticaButtonEntity.TOOLS_OF_TRADE,
        press_fn=lambda habitica: habitica.cast_skill(Skill.TOOLS_OF_THE_TRADE),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 13
            and (data.user.stats.mp or 0) >= 25
        ),
        class_needed=HabiticaClass.ROGUE,
        entity_picture="shop_toolsOfTrade.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.STEALTH,
        translation_key=HabiticaButtonEntity.STEALTH,
        press_fn=lambda habitica: habitica.cast_skill(Skill.STEALTH),
        # Stealth buffs stack and it can only be cast if the amount of
        # buffs is smaller than the amount of unfinished dailies
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 14
            and (data.user.stats.mp or 0) >= 45
            and (data.user.stats.buffs.stealth or 0)
            < len(
                [
                    r
                    for r in data.tasks
                    if r.Type is TaskType.DAILY
                    and r.isDue is True
                    and r.completed is False
                ]
            )
        ),
        class_needed=HabiticaClass.ROGUE,
        entity_picture="shop_stealth.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.HEAL,
        translation_key=HabiticaButtonEntity.HEAL,
        press_fn=lambda habitica: habitica.cast_skill(Skill.HEALING_LIGHT),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 11
            and (data.user.stats.mp or 0) >= 15
            and (data.user.stats.hp or 0) < 50
        ),
        class_needed=HabiticaClass.HEALER,
        entity_picture="shop_heal.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.BRIGHTNESS,
        translation_key=HabiticaButtonEntity.BRIGHTNESS,
        press_fn=lambda habitica: habitica.cast_skill(Skill.SEARING_BRIGHTNESS),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 12
            and (data.user.stats.mp or 0) >= 15
        ),
        class_needed=HabiticaClass.HEALER,
        entity_picture="shop_brightness.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.PROTECT_AURA,
        translation_key=HabiticaButtonEntity.PROTECT_AURA,
        press_fn=lambda habitica: habitica.cast_skill(Skill.PROTECTIVE_AURA),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 13
            and (data.user.stats.mp or 0) >= 30
        ),
        class_needed=HabiticaClass.HEALER,
        entity_picture="shop_protectAura.png",
    ),
    HabiticaButtonEntityDescription(
        key=HabiticaButtonEntity.HEAL_ALL,
        translation_key=HabiticaButtonEntity.HEAL_ALL,
        press_fn=lambda habitica: habitica.cast_skill(Skill.BLESSING),
        available_fn=(
            lambda data: (data.user.stats.lvl or 0) >= 14
            and (data.user.stats.mp or 0) >= 25
        ),
        class_needed=HabiticaClass.HEALER,
        entity_picture="shop_healAll.png",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""

    coordinator = entry.runtime_data
    skills_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add or remove a skillset based on the player's class."""

        nonlocal skills_added
        buttons = []
        entity_registry = er.async_get(hass)

        for description in CLASS_SKILLS:
            if (
                (coordinator.data.user.stats.lvl or 0) >= 10
                and coordinator.data.user.flags.classSelected
                and not coordinator.data.user.preferences.disableClasses
                and description.class_needed is coordinator.data.user.stats.Class
            ):
                if description.key not in skills_added:
                    buttons.append(HabiticaButton(coordinator, description))
                    skills_added.add(description.key)
            elif description.key in skills_added:
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_{description.key}",
                ):
                    entity_registry.async_remove(entity_id)
                skills_added.remove(description.key)

        if buttons:
            async_add_entities(buttons)

    coordinator.async_add_listener(add_entities)
    add_entities()

    async_add_entities(
        HabiticaButton(coordinator, description) for description in BUTTON_DESCRIPTIONS
    )

    # Add individual habit buttons with dynamic management
    habits_added: set[str] = set()

    @callback
    def add_habit_buttons() -> None:
        """Add or remove habit buttons based on coordinator data."""
        nonlocal habits_added
        buttons = []
        entity_registry = er.async_get(hass)

        current_habits = set()
        if coordinator.data and coordinator.data.habits:
            for habit in coordinator.data.habits:
                if habit and habit.id:
                    habit_id = str(habit.id)
                    current_habits.add(habit_id)

                    # Add new habit buttons if not already added
                    if habit_id not in habits_added:
                        buttons.append(HabiticaHabitButton(coordinator, habit, "up"))
                        buttons.append(HabiticaHabitButton(coordinator, habit, "down"))
                        habits_added.add(habit_id)

        # Remove buttons for habits that no longer exist
        for habit_id in habits_added.copy():
            if habit_id not in current_habits:
                # Remove up button
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_habit_{habit_id}_up",
                ):
                    entity_registry.async_remove(entity_id)
                # Remove down button
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN,
                    DOMAIN,
                    f"{coordinator.config_entry.unique_id}_habit_{habit_id}_down",
                ):
                    entity_registry.async_remove(entity_id)
                habits_added.remove(habit_id)

        if buttons:
            async_add_entities(buttons)

    coordinator.async_add_listener(add_habit_buttons)
    add_habit_buttons()


class HabiticaButton(HabiticaBase, ButtonEntity):
    """Representation of a Habitica button."""

    entity_description: HabiticaButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.coordinator.execute(self.entity_description.press_fn)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Is entity available."""

        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if entity_picture := self.entity_description.entity_picture:
            return f"{ASSETS_URL}{entity_picture}"
        return None


class HabiticaHabitButton(
    CoordinatorEntity[HabiticaDataUpdateCoordinator], ButtonEntity
):
    """Button for scoring Habitica habits."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        habit: Any,
        direction: str,
    ) -> None:
        """Initialize the habit button."""
        super().__init__(coordinator)
        self.habit = habit
        self.direction = direction
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_habit_{habit.id}_{direction}"
        )
        self._attr_name = f"{habit.text} ({direction})"
        self._attr_icon = "mdi:plus" if direction == "up" else "mdi:minus"

        # Set device info to link to the main Habitica device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )

    def _get_habit_sensor(self) -> Any | None:
        """Get the corresponding habit sensor from registry."""
        config_entry_id = self.coordinator.config_entry.entry_id
        habit_id = str(self.habit.id)
        return (
            self.hass.data.get(DATA_HABIT_SENSORS, {})
            .get(config_entry_id, {})
            .get(habit_id)
        )

    async def async_press(self) -> None:
        """Handle button press to score habit."""
        direction_value = Direction.UP if self.direction == "up" else Direction.DOWN

        # Optimistic update: immediately update the sensor for responsive UI
        estimated_delta = (
            OPTIMISTIC_HABIT_SCORE_DELTA
            if self.direction == "up"
            else -OPTIMISTIC_HABIT_SCORE_DELTA
        )

        # Find the corresponding sensor and trigger optimistic update
        if sensor := self._get_habit_sensor():
            sensor.set_optimistic_update(estimated_delta, self.direction)

        # Execute the actual API call (this will trigger coordinator refresh after)
        await self.coordinator.execute(
            lambda habitica: habitica.update_score(self.habit.id, direction_value)
        )

    @property
    def available(self) -> bool:
        """Return if button is available."""
        if not super().available or not self.coordinator.data:
            return False

        # Check if habit still exists and allows this direction
        for current_habit in self.coordinator.data.habits:
            if current_habit and current_habit.id == self.habit.id:
                if self.direction == "up":
                    return getattr(current_habit, "up", True)
                return getattr(current_habit, "down", True)
        return False
