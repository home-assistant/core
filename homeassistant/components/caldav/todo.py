"""CalDAV todo platform."""

import asyncio
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from functools import partial
import logging
from typing import Any, NamedTuple, cast, override

from caldav.calendarobjectresource import CalendarObjectResource, Todo
from caldav.collection import Calendar, SynchronizableCalendarObjectCollection
from caldav.elements import dav
from caldav.lib.error import (
    ConsistencyError,
    DAVError,
    ETagMismatchError,
    NotFoundError,
    ScheduleTagMismatchError,
)
from caldav.lib.http_sync import requests as caldav_requests

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CalDavConfigEntry
from .api import calendars_supporting, get_attr_value
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)
# A restored server may report no changes for a sync token it never issued
MAX_SKIPPED_UPDATES = 3
# Nextcloud Tasks and Tasks.org count X-APPLE-SORT-ORDER in seconds from 2001
SORT_ORDER_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)
SORT_ORDER_GAP = 1024

SUPPORTED_COMPONENT = "VTODO"
TODO_STATUS_MAP = {
    "NEEDS-ACTION": TodoItemStatus.NEEDS_ACTION,
    "IN-PROCESS": TodoItemStatus.NEEDS_ACTION,
    "COMPLETED": TodoItemStatus.COMPLETED,
    "CANCELLED": TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV: dict[TodoItemStatus, str] = {
    TodoItemStatus.NEEDS_ACTION: "NEEDS-ACTION",
    TodoItemStatus.COMPLETED: "COMPLETED",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalDavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CalDav todo platform for a config entry."""
    calendars = calendars_supporting(entry.runtime_data.calendars, SUPPORTED_COMPONENT)
    async_add_entities(
        (
            WebDavTodoListEntity(
                calendar,
                calendar_name,
                entry.entry_id,
            )
            for calendar, calendar_name in calendars
        ),
        True,
    )


def _get_changes(calendar: Calendar, sync_token: str | None) -> tuple[bool, str | None]:
    """Return whether a calendar changed since the sync token, and the new token.

    A failed sync-collection report (RFC 6578) counts as changed.
    """
    try:
        changes = cast(
            SynchronizableCalendarObjectCollection,
            calendar.get_objects_by_sync_token(sync_token, disable_fallback=True),
        )
    except (caldav_requests.exceptions.RequestException, DAVError) as err:
        _LOGGER.debug("Cannot read the changes, reading all items: %s", err)
        return True, None
    # A token with second precision can stay the same, but the change is listed
    changed = sync_token is None or changes.sync_token != sync_token or len(changes) > 0
    return changed, changes.sync_token


class _SortedTodo(NamedTuple):
    """A todo with its position in the list."""

    resource: CalendarObjectResource
    data: str
    item: TodoItem
    position: int


def _get_todos(calendar: Calendar) -> list[_SortedTodo]:
    """Fetch and parse todo items, in list order."""
    results = cast(
        list[CalendarObjectResource],
        calendar.search(todo=True, include_completed=True),
    )
    todos = []
    for resource in results:
        data = resource.data
        if (todo_item := _todo_item(resource)) is not None:
            position = _sort_position(resource.vobject_instance.vtodo)
            todos.append(_SortedTodo(resource, data, todo_item, position))
    return sorted(todos, key=lambda todo: todo.position)


def _strong_etag(todo: CalendarObjectResource) -> str | None:
    """Return the ETag of a todo, None if it is weak."""
    # If-Match never matches a weak ETag (RFC 9110 section 13.1.1)
    if (etag := todo.etag) and not etag.startswith("W/"):
        return etag
    return None


def _get_etags(todos: list[_SortedTodo]) -> dict[str, str]:
    """Return the ETag of each todo by its URL."""
    return {
        str(todo.resource.url): etag
        for todo in todos
        if (etag := _strong_etag(todo.resource)) is not None
    }


def _expect_listed(todo: CalendarObjectResource, etags: dict[str, str]) -> None:
    """Raise if a todo is not the version listed, and make its save expect that version."""
    if (etag := etags.get(str(todo.url))) is None:
        return
    if todo.etag not in (None, etag):
        raise ETagMismatchError
    todo.props[dav.GetEtag.tag] = etag


def _sort_position(todo: Any) -> int:
    """Return the position of a todo, its creation time if it has none."""
    if (sort_order := get_attr_value(todo, "x_apple_sort_order")) is not None:
        with suppress(ValueError):
            return int(sort_order)
    if isinstance(created := get_attr_value(todo, "created"), datetime):
        return _seconds_since_epoch(created)
    return 0


def _seconds_since_epoch(value: datetime) -> int:
    """Return a time as a position, one without a time zone as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int((value - SORT_ORDER_EPOCH).total_seconds())


def _set_position(todo: _SortedTodo, position: int) -> None:
    """Write a position into the todo as the server sent it, not as vobject parsed it.

    vobject drops what follows a comma in some values.
    """
    todo.resource.data = todo.data
    todo.resource.icalendar_component["X-APPLE-SORT-ORDER"] = str(position)


def _move_todo(
    calendar: Calendar, uid: str, previous_uid: str | None
) -> tuple[list[TodoItem], list[CalendarObjectResource]]:
    """Give a todo a position behind another one.

    Returns the list as read, and the todos to save. The todo goes between its
    new neighbors with room left on both sides. Where they leave no room, it
    and the todos behind it are spread out up to the next todo with room, or
    at the end up to now, where new todos are added. The todos to save are
    returned from the back, so the moved todo takes its place once there is
    room.
    """
    todos = _get_todos(calendar)
    items = [todo.item for todo in todos]
    uids = [item.uid for item in items]
    for wanted in (uid, previous_uid):
        if wanted is not None and wanted not in uids:
            raise HomeAssistantError(f"Could not find To-do item {wanted}")
    moved = todos.pop(uids.index(uid))
    uids.remove(uid)
    todos.insert(0 if previous_uid is None else uids.index(previous_uid) + 1, moved)
    # Open and completed todos are ordered apart, as the to-do list card shows them
    group = [todo for todo in todos if todo.item.status == moved.item.status]
    index = group.index(moved)
    before = group[index - 1].position if index else None
    after = group[index + 1].position if index + 1 < len(group) else None
    if before is None:
        if after is None or moved.position < after:
            return items, []
        _set_position(moved, after - SORT_ORDER_GAP)
        return items, [moved.resource]
    if before < moved.position and (after is None or moved.position < after):
        return items, []
    spread = [moved]
    limit = _seconds_since_epoch(dt_util.utcnow())
    for todo in group[index + 1 :]:
        if todo.position - before > len(spread):
            limit = todo.position
            break
        spread.append(todo)
    step = max(1, min(SORT_ORDER_GAP, (limit - before) // (len(spread) + 1)))
    for count, todo in enumerate(spread, 1):
        _set_position(todo, before + step * count)
    return items, [todo.resource for todo in reversed(spread)]


def _save_todos(todos: list[CalendarObjectResource]) -> None:
    """Save todos in order, stopping at the first that fails."""
    for todo in todos:
        todo.save(increase_seqno=False, only_this_recurrence=False)


def _todo_item(resource: CalendarObjectResource) -> TodoItem | None:
    """Convert a caldav Todo into a TodoItem."""
    if (
        not hasattr(resource.vobject_instance, "vtodo")
        or not (todo := resource.vobject_instance.vtodo)
        or (uid := get_attr_value(todo, "uid")) is None
        or (summary := get_attr_value(todo, "summary")) is None
    ):
        return None
    due: date | datetime | None = None
    if due_value := get_attr_value(todo, "due"):
        if isinstance(due_value, datetime):
            due = dt_util.as_local(due_value)
        elif isinstance(due_value, date):
            due = due_value
    status = TODO_STATUS_MAP.get(
        get_attr_value(todo, "status") or "",
        TodoItemStatus.NEEDS_ACTION,
    )
    completed: datetime | None = None
    if status == TodoItemStatus.COMPLETED and isinstance(
        completed_value := get_attr_value(todo, "completed"), datetime
    ):
        completed = dt_util.as_local(completed_value)
    return TodoItem(
        uid=uid,
        summary=summary,
        status=status,
        due=due,
        description=get_attr_value(todo, "description"),
        completed=completed,
    )


class WebDavTodoListEntity(TodoListEntity):
    """CalDAV To-do list entity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self, calendar: Calendar, calendar_name: str | None, config_entry_id: str
    ) -> None:
        """Initialize WebDavTodoListEntity."""
        self._calendar = calendar
        self._attr_name = (calendar_name or "Unknown").capitalize()
        self._attr_unique_id = f"{config_entry_id}-{calendar.id}"
        self._sync_token: str | None = None
        self._etags: dict[str, str] = {}
        self._skips_left = 0
        self._writes = 0
        self._writes_seen = 0
        self._write_lock = asyncio.Lock()

    async def async_update(self) -> None:
        """Update To-do list entity state.

        A write during the full read had its refresh dropped while this update
        ran, so another refresh follows once it is done. The items and ETags of
        that read may be from before the write and are not kept.
        """
        changed, sync_token = await self.hass.async_add_executor_job(
            _get_changes, self._calendar, self._sync_token
        )
        writes = self._writes
        if not changed and self._skips_left and writes == self._writes_seen:
            self._skips_left -= 1
            return
        todos = await self.hass.async_add_executor_job(_get_todos, self._calendar)
        todo_items = [todo.item for todo in todos]
        if not changed and todo_items != self._attr_todo_items:
            # The report missed a change
            sync_token = None
        if self._writes == writes:
            self._attr_todo_items = todo_items
            self._etags = _get_etags(todos)
        self._sync_token = sync_token
        self._skips_left = MAX_SKIPPED_UPDATES
        self._writes_seen = writes
        if self._writes != writes:
            self.hass.async_create_task(
                self.async_update_ha_state(force_refresh=True), eager_start=False
            )

    def _expect_saved(self, todo: CalendarObjectResource) -> None:
        """Expect the saved version in later writes, if the server named it."""
        # A strong ETag is only allowed for data stored as sent (RFC 4791 section 5.3.4)
        if (etag := _strong_etag(todo)) is None:
            self._etags.pop(str(todo.url), None)
        else:
            self._etags[str(todo.url)] = etag

    def _replace_listed(self, todo: CalendarObjectResource) -> None:
        """Show a todo as saved until the list is read again."""
        self._expect_saved(todo)
        if (saved := _todo_item(todo)) is not None and self._attr_todo_items:
            self._attr_todo_items = [
                saved if item.uid == saved.uid else item
                for item in self._attr_todo_items
            ]

    def _item_changed(self) -> HomeAssistantError:
        """Read the list again, and return the error for an item changed elsewhere."""
        self._writes += 1
        self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))
        return HomeAssistantError(
            translation_domain=DOMAIN, translation_key="item_changed"
        )

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        item_data: dict[str, Any] = {"created": dt_util.utcnow()}
        if summary := item.summary:
            item_data["summary"] = summary
        if status := item.status:
            item_data["status"] = TODO_STATUS_MAP_INV.get(status, "NEEDS-ACTION")
        if due := item.due:
            item_data["due"] = due
        if description := item.description:
            item_data["description"] = description
        try:
            await self.hass.async_add_executor_job(
                partial(self._calendar.add_todo, **item_data),
            )
            self._writes += 1
            # refreshing async otherwise it would take too much time
            self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV save error: {err}") from err

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        etags = dict(self._etags)
        async with self._write_lock:
            uid: str = cast(str, item.uid)
            try:
                todo = cast(
                    Todo,
                    await self.hass.async_add_executor_job(
                        self._calendar.get_todo_by_uid, uid
                    ),
                )
            except NotFoundError as err:
                raise self._item_changed() from err
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                raise HomeAssistantError(f"CalDAV lookup error: {err}") from err
            vtodo = todo.icalendar_component
            vtodo["SUMMARY"] = item.summary or ""
            if status := item.status:
                previous = TODO_STATUS_MAP.get(
                    vtodo.get("STATUS", ""), TodoItemStatus.NEEDS_ACTION
                )
                vtodo["STATUS"] = TODO_STATUS_MAP_INV.get(status, "NEEDS-ACTION")
                if status != TodoItemStatus.COMPLETED:
                    vtodo.pop("COMPLETED", None)
                elif previous != TodoItemStatus.COMPLETED:
                    vtodo.pop("COMPLETED", None)
                    vtodo.add("COMPLETED", dt_util.utcnow())
            if due := item.due:
                todo.set_due(due)
            else:
                vtodo.pop("DUE", None)
            if description := item.description:
                vtodo["DESCRIPTION"] = description
            else:
                vtodo.pop("DESCRIPTION", None)
            try:
                _expect_listed(todo, etags)
                await self.hass.async_add_executor_job(
                    partial(
                        todo.save,
                        no_create=True,
                        obj_type="todo",
                        only_this_recurrence=False,
                        precondition="etag",
                    ),
                )
                self._writes += 1
                self._replace_listed(todo)
                # refreshing async otherwise it would take too much time
                self.hass.async_create_task(
                    self.async_update_ha_state(force_refresh=True)
                )
            # caldav raises ConsistencyError for a todo that is gone by then
            except (
                ConsistencyError,
                ETagMismatchError,
                ScheduleTagMismatchError,
            ) as err:
                raise self._item_changed() from err
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                # A save that failed may still have been applied
                self._writes += 1
                self.hass.async_create_task(
                    self.async_update_ha_state(force_refresh=True)
                )
                raise HomeAssistantError(f"CalDAV save error: {err}") from err

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete To-do items."""
        etags = dict(self._etags)
        async with self._write_lock:
            tasks = (
                self.hass.async_add_executor_job(self._calendar.get_todo_by_uid, uid)
                for uid in uids
            )

            try:
                items = cast(list[Todo], await asyncio.gather(*tasks))
            except NotFoundError as err:
                raise self._item_changed() from err
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                raise HomeAssistantError(f"CalDAV lookup error: {err}") from err

            deleted = 0

            def delete_items() -> None:
                """Delete the items one by one."""
                nonlocal deleted
                # Run serially as some CalDAV servers do not support concurrent changes
                for item in items:
                    item.delete(if_match=etags.get(str(item.url)))
                    deleted += 1

            try:
                # SOGo deletes an item whatever If-Match says
                for item in items:
                    _expect_listed(item, etags)
                await self.hass.async_add_executor_job(delete_items)
            # caldav raises on a 404 only if the delete is conditional
            except (ETagMismatchError, NotFoundError) as err:
                raise self._item_changed() from err
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                raise HomeAssistantError(f"CalDAV delete error: {err}") from err
            finally:
                # A delete that fails part-way still changed the list
                self._writes += deleted
            # refreshing async otherwise it would take too much time
            self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))

    @override
    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move a To-do item behind another one, or to the top.

        A list read for the move that is not the one shown, for example without
        an item deleted elsewhere, counts as changed, so the refresh reads it in
        full even if the sync report missed that change.
        """
        if uid == previous_uid:
            return
        async with self._write_lock:
            try:
                items, todos = await self.hass.async_add_executor_job(
                    _move_todo, self._calendar, uid, previous_uid
                )
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
                ValueError,
            ) as err:
                raise HomeAssistantError(f"CalDAV lookup error: {err}") from err
            except HomeAssistantError:
                self._writes += 1
                self.hass.async_create_task(
                    self.async_update_ha_state(force_refresh=True)
                )
                raise
            if items != self._attr_todo_items:
                self._writes += 1
            shown = {
                str(todo.url)
                for todo in todos
                if (etag := _strong_etag(todo)) is not None
                and self._etags.get(str(todo.url)) == etag
            }
            try:
                await self.hass.async_add_executor_job(_save_todos, todos)
                if todos:
                    self._writes += 1
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                # A save that failed may still have been applied
                self._writes += 1
                raise HomeAssistantError(f"CalDAV save error: {err}") from err
            finally:
                for todo in todos:
                    if str(todo.url) in shown:
                        self._expect_saved(todo)
                self.hass.async_create_task(
                    self.async_update_ha_state(force_refresh=True)
                )
