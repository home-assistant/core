"""Todo platform for the Habitica integration."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from aiohttp import ClientError
from habiticalib import Direction, HabiticaException, Task, TaskType

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

from .const import ASSETS_URL, DOMAIN
from .coordinator import HabiticaDataUpdateCoordinator
from .entity import HabiticaBase
from .types import HabiticaConfigEntry
from .util import next_due_date

PARALLEL_UPDATES = 1


class HabiticaTodoList(StrEnum):
    """Habitica Entities."""

    HABITS = "habits"
    DAILIES = "dailys"
    TODOS = "todos"
    REWARDS = "rewards"


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
        if len(uids) > 1 and self.entity_description.key is HabiticaTodoList.TODOS:
            try:
                await self.coordinator.habitica.delete_completed_todos()
            except (HabiticaException, ClientError) as e:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="delete_completed_todos_failed",
                ) from e
        else:
            for task_id in uids:
                try:
                    await self.coordinator.habitica.delete_task(UUID(task_id))
                except (HabiticaException, ClientError) as e:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key=f"delete_{self.entity_description.key}_failed",
                    ) from e

        await self.coordinator.async_request_refresh()

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
            await self.coordinator.habitica.reorder_task(UUID(uid), pos)
        except (HabiticaException, ClientError) as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"move_{self.entity_description.key}_item_failed",
                translation_placeholders={"pos": str(pos)},
            ) from e
        else:
            # move tasks in the coordinator until we have fresh data
            tasks = self.coordinator.data.tasks
            new_pos = (
                tasks.index(
                    next(task for task in tasks if task.id == UUID(previous_uid))
                )
                + 1
                if previous_uid
                else 0
            )
            old_pos = tasks.index(next(task for task in tasks if task.id == UUID(uid)))
            tasks.insert(new_pos, tasks.pop(old_pos))
            await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a Habitica todo."""
        refresh_required = False
        current_item = next(
            (task for task in (self.todo_items or []) if task.uid == item.uid),
            None,
        )

        if TYPE_CHECKING:
            assert item.uid
            assert current_item
            assert item.summary

        task = Task(
            text=item.summary,
            notes=item.description or "",
        )

        if (
            self.entity_description.key is HabiticaTodoList.TODOS
        ):  # Only todos support a due date.
            task["date"] = item.due

        if (
            item.summary != current_item.summary
            or item.description != current_item.description
            or item.due != current_item.due
        ):
            try:
                await self.coordinator.habitica.update_task(UUID(item.uid), task)
                refresh_required = True
            except (HabiticaException, ClientError) as e:
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
                score_result = await self.coordinator.habitica.update_score(
                    UUID(item.uid), Direction.UP
                )
                refresh_required = True
            elif (
                current_item.status is TodoItemStatus.COMPLETED
                and item.status == TodoItemStatus.NEEDS_ACTION
            ):
                score_result = await self.coordinator.habitica.update_score(
                    UUID(item.uid), Direction.DOWN
                )
                refresh_required = True
            else:
                score_result = None

        except (HabiticaException, ClientError) as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"score_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        if score_result and score_result.data.tmp.drop.key:
            drop = score_result.data.tmp.drop
            msg = (
                f"![{drop.key}]({ASSETS_URL}Pet_{drop.Type}_{drop.key}.png)\n"
                f"{drop.dialog}"
            )
            persistent_notification.async_create(
                self.hass, message=msg, title="Habitica"
            )
        if refresh_required:
            await self.coordinator.async_request_refresh()


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
                    uid=str(task.id),
                    summary=task.text,
                    description=task.notes,
                    due=dt_util.as_local(task.date).date() if task.date else None,
                    status=(
                        TodoItemStatus.NEEDS_ACTION
                        if not task.completed
                        else TodoItemStatus.COMPLETED
                    ),
                )
                for task in self.coordinator.data.tasks
                if task.Type is TaskType.TODO
            ),
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a Habitica todo."""
        if TYPE_CHECKING:
            assert item.summary
            assert item.description
        try:
            await self.coordinator.habitica.create_task(
                Task(
                    text=item.summary,
                    type=TaskType.TODO,
                    notes=item.description,
                    date=item.due,
                )
            )
        except (HabiticaException, ClientError) as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"create_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        await self.coordinator.async_request_refresh()


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
        if TYPE_CHECKING:
            assert self.coordinator.data.user.lastCron

        return [
            *(
                TodoItem(
                    uid=str(task.id),
                    summary=task.text,
                    description=task.notes,
                    due=next_due_date(task, self.coordinator.data.user.lastCron),
                    status=(
                        TodoItemStatus.COMPLETED
                        if task.completed
                        else TodoItemStatus.NEEDS_ACTION
                    ),
                )
                for task in self.coordinator.data.tasks
                if task.Type is TaskType.DAILY
            )
        ]
