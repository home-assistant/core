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
        for uid in uids:
            task = next(
                task for task in self.coordinator.data.tasks if task.id == UUID(uid)
            )
            self.coordinator.data.tasks.remove(task)

            if task.id and not task.completed:
                self.coordinator.data.user.tasksOrder.todos.remove(task.id)

        self.async_write_ha_state()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move an item in the To-do list."""

        task_order = (
            self.coordinator.data.user.tasksOrder.todos
            if self.entity_description.key is HabiticaTodoList.TODOS
            else self.coordinator.data.user.tasksOrder.dailys
        )
        if previous_uid:
            cur_pos = task_order.index(UUID(uid))
            prev_pos = task_order.index(UUID(previous_uid))
            offset = 0 if cur_pos < prev_pos else 1
            pos = prev_pos + offset
        else:
            pos = 0

        try:
            task_order = (
                await self.coordinator.habitica.reorder_task(UUID(uid), pos)
            ).data
        except (HabiticaException, ClientError) as e:
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
        current_task = next(
            task for task in self.coordinator.data.tasks if task.id == UUID(item.uid)
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
                current_task = (
                    await self.coordinator.habitica.update_task(UUID(item.uid), task)
                ).data

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
                current_task.completed = True

            elif (
                current_item.status is TodoItemStatus.COMPLETED
                and item.status == TodoItemStatus.NEEDS_ACTION
            ):
                score_result = await self.coordinator.habitica.update_score(
                    UUID(item.uid), Direction.DOWN
                )
                current_task.completed = False
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
        if score_result:
            for field in self.coordinator.data.user.stats.__annotations__:
                if (value := getattr(score_result.data, field)) is not None:
                    setattr(self.coordinator.data.user.stats, field, value)

        self.coordinator.async_update_listeners()


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

        tasks = [
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

        return sorted(
            tasks,
            key=lambda task: (
                float("inf")
                if (uid := (UUID(task.uid)))
                not in (tasks_order := self.coordinator.data.user.tasksOrder.todos)
                else tasks_order.index(uid)
            ),
        )

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a Habitica todo."""
        if TYPE_CHECKING:
            assert item.summary
            assert item.description
        try:
            data = (
                await self.coordinator.habitica.create_task(
                    Task(
                        text=item.summary,
                        type=TaskType.TODO,
                        notes=item.description,
                        date=item.due,
                    )
                )
            ).data

        except (HabiticaException, ClientError) as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"create_{self.entity_description.key}_item_failed",
                translation_placeholders={"name": item.summary or ""},
            ) from e

        self.coordinator.data.tasks.append(data)
        if TYPE_CHECKING:
            assert data.id
        self.coordinator.data.user.tasksOrder.todos.insert(0, data.id)
        self.async_write_ha_state()


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

        tasks = [
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

        return sorted(
            tasks,
            key=lambda task: (
                self.coordinator.data.user.tasksOrder.dailys.index(UUID(task.uid))
            ),
        )
