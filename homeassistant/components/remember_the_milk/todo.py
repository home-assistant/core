"""A todo platform for Remember The Milk."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, cast, override

from aiortm import AioRTMError, AuthError

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LIST_ID, DOMAIN, SUBENTRY_TYPE_LIST
from .coordinator import RememberTheMilkConfigEntry, RtmTodoCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RememberTheMilkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the RTM todo platform."""
    coordinator = entry.runtime_data.coordinator
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIST):
        async_add_entities(
            [RtmTodoListEntity(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


def handle_api_errors[**_P](
    func: Callable[_P, Awaitable[None]],
) -> Callable[_P, Coroutine[Any, Any, None]]:
    """Catch aiortm errors and re-raise as HomeAssistantError."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except AuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except AioRTMError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    return wrapper


class RtmTodoListEntity(CoordinatorEntity[RtmTodoCoordinator], TodoListEntity):
    """A Remember The Milk TodoListEntity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self,
        coordinator: RtmTodoCoordinator,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the RtmTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self._list_id: int = subentry.data[CONF_LIST_ID]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Remember The Milk",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    @override
    def todo_items(self) -> list[TodoItem]:
        """Return the To-do items in the To-do list."""
        rtm_list = self.coordinator.data.get(self._list_id)
        return [
            rtm_task.todo_item
            for rtm_task in (rtm_list.tasks.values() if rtm_list else [])
        ]

    @handle_api_errors
    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a To-do item."""
        client = self.coordinator.client
        timeline_response = await client.rtm.timelines.create()
        timeline = timeline_response.timeline
        if TYPE_CHECKING:
            assert item.summary is not None
        result = await client.rtm.tasks.add(
            timeline=timeline,
            name=item.summary,
            list_id=self._list_id,
            parse=True,
        )
        taskseries = result.task_list.taskseries[0]
        task = taskseries.task[0]
        if item.due is not None:
            await client.rtm.tasks.set_due_date(
                timeline=timeline,
                list_id=result.task_list.id,
                taskseries_id=taskseries.id,
                task_id=task.id,
                due=(
                    item.due if isinstance(item.due, datetime) else item.due.isoformat()
                ),
                has_due_time=isinstance(item.due, datetime),
            )
        if item.description:
            await client.rtm.tasks.notes.add(
                timeline=timeline,
                list_id=result.task_list.id,
                taskseries_id=taskseries.id,
                task_id=task.id,
                title="",
                text=item.description,
            )
        await self.coordinator.async_refresh()

    @handle_api_errors
    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid = cast(str, item.uid)
        list_id, taskseries_id, task_id = _parse_uid(uid)
        rtm_list = self.coordinator.data.get(self._list_id)
        existing = rtm_list.tasks.get(uid) if rtm_list else None
        client = self.coordinator.client
        timeline_response = await client.rtm.timelines.create()
        timeline = timeline_response.timeline

        if item.summary is not None:
            await client.rtm.tasks.set_name(
                timeline=timeline,
                list_id=list_id,
                taskseries_id=taskseries_id,
                task_id=task_id,
                name=item.summary,
            )

        if item.status is not None:
            if item.status == TodoItemStatus.COMPLETED:
                await client.rtm.tasks.complete(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                )
            else:
                await client.rtm.tasks.uncomplete(  # codespell:ignore uncomplete
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                )

        await client.rtm.tasks.set_due_date(
            timeline=timeline,
            list_id=list_id,
            taskseries_id=taskseries_id,
            task_id=task_id,
            due=(
                item.due
                if isinstance(item.due, (datetime, type(None)))
                else item.due.isoformat()
            ),
            has_due_time=(
                isinstance(item.due, datetime) if item.due is not None else None
            ),
        )

        note_id = existing.note_id if existing else None
        new_description = item.description or None
        if new_description and note_id is not None:
            await client.rtm.tasks.notes.edit(
                timeline=timeline,
                note_id=note_id,
                title="",
                text=new_description,
            )
        elif new_description:
            await client.rtm.tasks.notes.add(
                timeline=timeline,
                list_id=list_id,
                taskseries_id=taskseries_id,
                task_id=task_id,
                title="",
                text=new_description,
            )
        elif (
            note_id is not None
            and existing is not None
            and existing.todo_item.description is not None
        ):
            await client.rtm.tasks.notes.delete(
                timeline=timeline,
                note_id=note_id,
            )
        await self.coordinator.async_refresh()

    @handle_api_errors
    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete To-do items."""
        client = self.coordinator.client
        timeline_response = await client.rtm.timelines.create()
        timeline = timeline_response.timeline
        await asyncio.gather(
            *[
                client.rtm.tasks.delete(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                )
                for uid in uids
                for list_id, taskseries_id, task_id in (_parse_uid(uid),)
            ]
        )
        await self.coordinator.async_refresh()


def _parse_uid(uid: str) -> tuple[int, int, int]:
    """Split a task UID into (list_id, taskseries_id, task_id)."""
    parts = uid.split("_", 2)
    return int(parts[0]), int(parts[1]), int(parts[2])
