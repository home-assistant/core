"""Todo platform for the Habitica integration."""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, NAME
from .sensor import HabitipyData


class HabiticaTodoList(StrEnum):
    """Habitica Entities."""

    HABITS = "habits"
    DAILIES = "dailys"
    TODOS = "todos"
    REWARDS = "rewards"


class HabiticaTaskType(StrEnum):
    """Habitica Entities."""

    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = HabitipyData(hass.data[DOMAIN][config_entry.entry_id])
    await coordinator.update()

    async_add_entities(
        [
            HabiticaTodosListEntity(coordinator, config_entry),
            HabiticaDailiesListEntity(coordinator, config_entry),
        ],
        True,
    )


class BaseHabiticaListEntity(TodoListEntity):
    """Representation of Habitica task lists."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HabitipyData, key: HabiticaTodoList, entry: ConfigEntry
    ) -> None:
        """Initialize HabiticaTodoListEntity."""
        if TYPE_CHECKING:
            assert entry.unique_id
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self.idx = key
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=entry.data[CONF_NAME],
            configuration_url=entry.data[CONF_URL],
            identifiers={(DOMAIN, entry.unique_id)},
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete Habitica tasks."""
        for taskId in uids:
            try:
                await self.coordinator.api.tasks[taskId].delete()
            except ClientResponseError as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=f"delete_{self.idx}_failed",
                ) from e

        await self.coordinator.update(no_throttle=True)
        self.async_schedule_update_ha_state()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move an item in the To-do list."""
        if TYPE_CHECKING:
            assert self.todo_items

        if previous_uid:
            pos = (
                self.todo_items.index(
                    next(item for item in self.todo_items if item.uid == previous_uid)
                )
                + 1
            )
        else:
            pos = 0

        try:
            await self.coordinator.api.tasks[uid].move.to[str(pos)].post()

        except ClientResponseError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"move_{self.idx}_item_failed",
                translation_placeholders={"pos": str(pos)},
            ) from e

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a Habitica todo."""
        current_item = next(
            (task for task in (self.todo_items or []) if task.uid == item.uid),
            None,
        )

        if TYPE_CHECKING:
            assert item.uid
            assert current_item

        try:
            await self.coordinator.api.tasks[item.uid].put(
                text=item.summary,
                notes=item.description or "",
                date=item.due.isoformat()
                if item.due
                and self.idx == HabiticaTodoList.TODOS  # Only todos support a due date.
                else None,
            )
        except ClientResponseError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"update_{self.idx}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        try:
            # Score up or down if item status changed
            if (
                current_item.status == TodoItemStatus.NEEDS_ACTION
                and item.status == TodoItemStatus.COMPLETED
            ):
                await self.coordinator.api.tasks[item.uid].score["up"].post()
            elif (
                current_item.status == TodoItemStatus.COMPLETED
                and item.status == TodoItemStatus.NEEDS_ACTION
            ):
                await self.coordinator.api.tasks[item.uid].score["down"].post()

        except ClientResponseError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"score_{self.idx}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.update(no_throttle=True)
        self.async_schedule_update_ha_state()


class HabiticaTodosListEntity(BaseHabiticaListEntity):
    """List of Habitica todos."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: HabitipyData, entry: ConfigEntry) -> None:
        """Initialize HabiticaTodosListEntity."""
        super().__init__(coordinator, HabiticaTodoList.TODOS, entry)

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the todo items."""

        return [
            *(
                TodoItem(
                    uid=task["id"],
                    summary=task["text"],
                    description=task["notes"],
                    due=(
                        dt_util.as_local(
                            datetime.datetime.fromisoformat(task.get("date"))
                        ).date()
                        if task.get("date")
                        else None
                    ),
                    status=TodoItemStatus.NEEDS_ACTION
                    if not task["completed"]
                    else TodoItemStatus.COMPLETED,
                )
                for task in self.coordinator.tasks.get(HabiticaTodoList.TODOS, [])
            ),
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a Habitica todo."""

        try:
            await self.coordinator.api.tasks.user.post(
                text=item.summary,
                type=HabiticaTaskType.TODO,
                notes=item.description,
                date=item.due.isoformat() if item.due else None,
            )
        except ClientResponseError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"create_{self.idx}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.update(no_throttle=True)
        self.async_schedule_update_ha_state()


class HabiticaDailiesListEntity(BaseHabiticaListEntity):
    """List of Habitica dailies."""

    _attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: HabitipyData, entry: ConfigEntry) -> None:
        """Initialize HabiticaDailiesListEntity."""
        super().__init__(coordinator, HabiticaTodoList.DAILIES, entry)

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the dailies.

        dailies don't have a date, but we still can show the next due date,
        which is a calculated value based on recurrence of the task.
        Changes to the date in Home Assistant will be ignored.
        """

        def next_due_date(task: dict[str, Any]) -> datetime.date | None:
            if task["isDue"] and not task["completed"]:
                return datetime.date.today()
            try:
                return dt_util.as_local(
                    datetime.datetime.fromisoformat(task["nextDue"][0])
                ).date()
            except (ValueError, IndexError):
                return None

        return [
            *(
                TodoItem(
                    uid=task["id"],
                    summary=task["text"],
                    description=task["notes"],
                    due=next_due_date(task),
                    status=TodoItemStatus.COMPLETED
                    if task["completed"]
                    else TodoItemStatus.NEEDS_ACTION,
                )
                for task in self.coordinator.tasks.get(HabiticaTodoList.DAILIES, [])
            )
        ]
