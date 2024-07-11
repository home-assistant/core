"""Todo platform for the Habitica integration."""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from aiohttp import ClientResponseError

from homeassistant.components import persistent_notification
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HabiticaConfigEntry
from .const import ASSETS_URL, DOMAIN
from .coordinator import HabiticaDataUpdateCoordinator
from .entity import HabiticaBase
from .util import next_due_date


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
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        [
            HabiticaTodosListEntity(coordinator),
            HabiticaDailiesListEntity(coordinator),
        ],
    )


class BaseHabiticaListEntity(HabiticaBase, TodoListEntity):
    """Representation of Habitica task lists."""

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
    ) -> None:
        """Initialize HabiticaTodoListEntity."""

        super().__init__(coordinator, self.entity_description)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete Habitica tasks."""
        for task_id in uids:
            try:
                await self.coordinator.api.tasks[task_id].delete()
            except ClientResponseError as e:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key=f"delete_{self.entity_description.key}_failed",
                ) from e

        await self.coordinator.async_refresh()

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
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"move_{self.entity_description.key}_item_failed",
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
            assert item.due

        if (
            self.entity_description.key is HabiticaTodoList.TODOS
            and item.due is not None
        ):  # Only todos support a due date.
            date = item.due.isoformat()
        else:
            date = None

        try:
            await self.coordinator.api.tasks[item.uid].put(
                text=item.summary,
                notes=item.description or "",
                date=date,
            )
        except ClientResponseError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"update_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        try:
            # Score up or down if item status changed
            if (
                current_item.status is TodoItemStatus.NEEDS_ACTION
                and item.status == TodoItemStatus.COMPLETED
            ):
                score_result = (
                    await self.coordinator.api.tasks[item.uid].score["up"].post()
                )
            elif (
                current_item.status is TodoItemStatus.COMPLETED
                and item.status == TodoItemStatus.NEEDS_ACTION
            ):
                score_result = (
                    await self.coordinator.api.tasks[item.uid].score["down"].post()
                )
            else:
                score_result = None

        except ClientResponseError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"score_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        if score_result and (drop := score_result.get("_tmp", {}).get("drop", False)):
            msg = (
                f"![{drop["key"]}]({ASSETS_URL}Pet_{drop["type"]}_{drop["key"]}.png)\n"
                f"{drop["dialog"]}"
            )
            persistent_notification.async_create(
                self.hass, message=msg, title="Habitica"
            )

        await self.coordinator.async_refresh()


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
    entity_description = EntityDescription(
        key=HabiticaTodoList.TODOS,
        translation_key=HabiticaTodoList.TODOS,
    )

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
                            datetime.datetime.fromisoformat(task["date"])
                        ).date()
                        if task.get("date")
                        else None
                    ),
                    status=(
                        TodoItemStatus.NEEDS_ACTION
                        if not task["completed"]
                        else TodoItemStatus.COMPLETED
                    ),
                )
                for task in self.coordinator.data.tasks
                if task["type"] == HabiticaTaskType.TODO
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
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"create_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_refresh()


class HabiticaDailiesListEntity(BaseHabiticaListEntity):
    """List of Habitica dailies."""

    _attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )
    entity_description = EntityDescription(
        key=HabiticaTodoList.DAILIES,
        translation_key=HabiticaTodoList.DAILIES,
    )

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the dailies.

        dailies don't have a date, but we still can show the next due date,
        which is a calculated value based on recurrence of the task.
        If a task is a yesterdaily, the due date is the last time
        a new day has been started. This allows to check off dailies from yesterday,
        that have been completed but forgotten to mark as completed before resetting the dailies.
        Changes of the date input field in Home Assistant will be ignored.
        """

        last_cron = self.coordinator.data.user["lastCron"]

        return [
            *(
                TodoItem(
                    uid=task["id"],
                    summary=task["text"],
                    description=task["notes"],
                    due=next_due_date(task, last_cron),
                    status=(
                        TodoItemStatus.COMPLETED
                        if task["completed"]
                        else TodoItemStatus.NEEDS_ACTION
                    ),
                )
                for task in self.coordinator.data.tasks
                if task["type"] == HabiticaTaskType.DAILY
            )
        ]
