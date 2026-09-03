"""Sensor platform for the Famn integration."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, override

from famn_sdk import LeaderboardEntry, MealItem, MealSlot, SpaceMember, TaskItem

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import (
    FamnChoresCoordinator,
    FamnConfigEntry,
    FamnMealPlanCoordinator,
    FamnScoresCoordinator,
)
from .entity import FamnEntity, famn_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FamnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform from a config entry."""
    coordinator = entry.runtime_data.chores
    known_lists: set[str] = set()

    async_add_entities([FamnDueTodaySensor(coordinator)])

    @callback
    def add_entities() -> None:
        """Add sensors for lists that appeared in Famn."""
        if new_lists := set(coordinator.data) - known_lists:
            async_add_entities(
                FamnListDueTodaySensor(coordinator, list_id) for list_id in new_lists
            )
            known_lists.update(new_lists)

    entry.async_on_unload(coordinator.async_add_listener(add_entities))
    add_entities()

    scores = entry.runtime_data.scores
    known_members: set[str] = set()

    @callback
    def add_member_sensors() -> None:
        """Add XP sensors for members that appeared in the space.

        The roster is the source, not the leaderboard: a member with no XP
        this season is absent from the leaderboard, so building from it
        would leave them without a sensor until they earn a point.
        """
        members = {
            member.id: member for member in scores.data.members if member.id is not None
        }
        if new_members := set(members) - known_members:
            async_add_entities(
                FamnMemberXPSensor(scores, members[member_id])
                for member_id in new_members
            )
            known_members.update(new_members)

    entry.async_on_unload(scores.async_add_listener(add_member_sensors))
    add_member_sensors()

    async_add_entities([FamnDinnerSensor(entry.runtime_data.meals)])


def _item_due(item: TaskItem) -> datetime | None:
    """Return when an open item is due, if it has a deadline at all."""
    return item.next_occurrence or item.due_date


def _count_items(items: list[TaskItem]) -> dict[str, int]:
    """Count a list's open items against the local calendar day."""
    now = dt_util.utcnow()
    end_of_today = dt_util.start_of_local_day() + timedelta(days=1)

    due_today = 0
    overdue = 0
    for item in items:
        due = _item_due(item)
        if due is None:
            continue
        if due < now:
            overdue += 1
        if due < end_of_today:
            due_today += 1
    return {"due_today": due_today, "overdue": overdue, "open": len(items)}


class FamnListDueTodaySensor(FamnEntity, SensorEntity):
    """How many of a list's items are due before the day ends.

    Overdue items count as due today — they still need doing today.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "list_due_today"

    def __init__(self, coordinator: FamnChoresCoordinator, list_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, list_id)
        self._attr_unique_id = f"{self._attr_unique_id}_due_today"
        self._attr_translation_placeholders = {
            "list_name": coordinator.data[list_id].task_list.name
        }

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the name in step with the list's name in Famn."""
        if (data := self.coordinator.data.get(self._key)) is not None:
            self._attr_translation_placeholders = {"list_name": data.task_list.name}
        super()._handle_coordinator_update()

    @property
    @override
    def native_value(self) -> int:
        """Return the number of items due before the end of today."""
        return _count_items(self.coordinator.data[self._key].items)["due_today"]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return open and overdue counts for the list."""
        counts = _count_items(self.coordinator.data[self._key].items)
        return {"overdue": counts["overdue"], "open_items": counts["open"]}


class FamnMemberXPSensor(CoordinatorEntity[FamnScoresCoordinator], SensorEntity):
    """A space member's XP in the current weekly season.

    Members without XP drop off the leaderboard when the season resets, so
    an absent member reads as 0 rather than unavailable — that is what a
    fresh Monday actually means.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "member_xp"
    _attr_native_unit_of_measurement = "XP"

    def __init__(self, coordinator: FamnScoresCoordinator, member: SpaceMember) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert member.id is not None
        self._member_id = member.id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{member.id}_xp"
        self._attr_translation_placeholders = {
            "member_name": member.display_name or member.id
        }
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the name in step with the member's display name in Famn."""
        if (member := self._member()) is not None:
            self._attr_translation_placeholders = {
                "member_name": member.display_name or self._member_id
            }
        super()._handle_coordinator_update()

    def _member(self) -> SpaceMember | None:
        """Return the member's current roster entry, if they are still there."""
        return next(
            (
                member
                for member in self.coordinator.data.members
                if member.id == self._member_id
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the member is still part of the Famn space."""
        return super().available and self._member() is not None

    def _entry(self) -> LeaderboardEntry | None:
        """Return the member's current leaderboard entry, if any."""
        return next(
            (
                entry
                for entry in self.coordinator.data.leaderboard
                if entry.space_member_id == self._member_id
            ),
            None,
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the member's XP this season."""
        entry = self._entry()
        return entry.total_xp or 0 if entry else 0

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rank, streaks, and the season window."""
        attributes: dict[str, Any] = {}
        if (entry := self._entry()) is not None:
            attributes = {
                "rank": entry.rank,
                "chores_completed": entry.chores_completed,
                "current_streak_days": entry.current_streak_days,
                "longest_streak_days": entry.longest_streak_days,
                "last_completed_at": entry.last_completed_at,
            }
        season = self.coordinator.data.season.season
        if season is not None:
            attributes["season_ends_at"] = season.ends_at
        return attributes


def _meal_item_title(item: MealItem) -> str | None:
    """Return what to call a meal item: the recipe name or its free text."""
    if item.recipe is not None and item.recipe.name:
        return item.recipe.name
    return item.title


def _recipe_image_url(image: str) -> str:
    """Return a renderable URL for a recipe image.

    Famn stores the Cloudflare Images delivery base URL; a variant suffix
    selects the rendition ("/public" is full size, the app's ICS export
    uses "/small" for thumbnails). Other image URLs pass through untouched.
    """
    if "imagedelivery.net" not in image:
        return image
    if image.rstrip("/").endswith(("/public", "/small")):
        return image
    return f"{image.rstrip('/')}/public"


class FamnDinnerSensor(CoordinatorEntity[FamnMealPlanCoordinator], SensorEntity):
    """What is for dinner tonight, straight from the Famn meal planner."""

    _attr_has_entity_name = True
    _attr_translation_key = "dinner_tonight"

    def __init__(self, coordinator: FamnMealPlanCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_dinner_tonight"
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    def _tonights_slot(self) -> MealSlot | None:
        """Return today's dinner slot, if one is planned."""
        today = dt_util.now().date()
        for slot in self.coordinator.data:
            if (
                slot.meal_type == "dinner"
                and slot.meal_date is not None
                and dt_util.as_local(slot.meal_date).date() == today
                and slot.status != "skipped"
            ):
                return slot
        return None

    @property
    @override
    def native_value(self) -> str | None:
        """Return tonight's dinner."""
        if (slot := self._tonights_slot()) is None:
            return None
        titles = [
            title for item in slot.items or [] if (title := _meal_item_title(item))
        ]
        return ", ".join(titles) if titles else slot.notes

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the recipe image of tonight's dinner."""
        if (slot := self._tonights_slot()) is None:
            return None
        for item in slot.items or []:
            if item.recipe is not None and item.recipe.image:
                return _recipe_image_url(item.recipe.image)
        return None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the slot details and recipe timings."""
        if (slot := self._tonights_slot()) is None:
            return {}
        attributes: dict[str, Any] = {
            "status": slot.status,
            "servings": slot.servings,
            "notes": slot.notes,
            "meal_date": slot.meal_date,
            "items": [
                title for item in slot.items or [] if (title := _meal_item_title(item))
            ],
        }
        for item in slot.items or []:
            if item.recipe is not None:
                attributes["prep_time"] = item.recipe.prep_time
                attributes["total_time"] = item.recipe.total_time
                break
        return attributes


class FamnDueTodaySensor(CoordinatorEntity[FamnChoresCoordinator], SensorEntity):
    """How many items across all lists are due before the day ends."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "due_today"

    def __init__(self, coordinator: FamnChoresCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_due_today"
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    @property
    @override
    def native_value(self) -> int:
        """Return the number of items due before the end of today."""
        return sum(
            _count_items(chore_list.items)["due_today"]
            for chore_list in self.coordinator.data.values()
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return open and overdue totals across all lists."""
        overdue = 0
        open_items = 0
        for chore_list in self.coordinator.data.values():
            counts = _count_items(chore_list.items)
            overdue += counts["overdue"]
            open_items += counts["open"]
        return {"overdue": overdue, "open_items": open_items}
