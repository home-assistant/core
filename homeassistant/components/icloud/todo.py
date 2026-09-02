"""Support for iCloud Reminders."""

from datetime import date, datetime
from typing import override

from pyicloud.services.reminders.service import RemindersService

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .account import IcloudConfigEntry
from .const import DOMAIN
from .coordinator import (
    REMINDERS_ERRORS,
    UNDECODED_TITLE,
    IcloudReminder,
    IcloudRemindersCoordinator,
)

# Every action is a blocking read-modify-write against one shared reminders
# service, so two concurrent calls could read the same reminder and then
# overwrite each other.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iCloud reminder lists."""
    coordinator = entry.runtime_data.reminders_coordinator
    assert coordinator is not None

    known: set[str] = set()

    @callback
    def _add_new_lists() -> None:
        """Add entities for lists that appeared since the last poll."""
        if not (new := set(coordinator.data or {}) - known):
            return
        known.update(new)
        async_add_entities(
            IcloudTodoListEntity(coordinator, entry, list_id) for list_id in new
        )

    _add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_lists))


class IcloudTodoListEntity(
    CoordinatorEntity[IcloudRemindersCoordinator], TodoListEntity
):
    """A reminder list from iCloud."""

    _attr_has_entity_name = True
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
        coordinator: IcloudRemindersCoordinator,
        entry: IcloudConfigEntry,
        list_id: str,
    ) -> None:
        """Initialize the reminder list."""
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_unique_id = f"{entry.unique_id}_{list_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_account")},
            manufacturer="Apple",
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the list still exists in iCloud."""
        return super().available and self._list_id in (self.coordinator.data or {})

    @property
    @override
    def name(self) -> str | None:
        """Return the name of the list."""
        if (
            reminder_list := (self.coordinator.data or {}).get(self._list_id)
        ) is not None:
            return reminder_list.name
        return None

    @property
    @override
    def todo_items(self) -> list[TodoItem] | None:
        """Return the reminders in this list.

        A subtask is an ordinary to-do item here, not a child of anything: the
        hierarchy only decides the order, so no entity model change is needed.
        """
        if (reminder_list := (self.coordinator.data or {}).get(self._list_id)) is None:
            return None
        return [_as_todo_item(item) for item in _ordered(reminder_list.reminders)]

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add a reminder to the list."""
        await self._async_call(self._create, item)

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a reminder."""
        if item.uid is None:
            raise HomeAssistantError("Cannot update a reminder without an identifier")

        await self._async_call(self._update, item)

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete reminders from the list."""
        await self._async_call(self._delete, uids)

    def _service(self) -> RemindersService:
        """Return the reminders service. Runs in the executor."""
        return self.coordinator.reminders

    def _create(self, item: TodoItem) -> None:
        """Create a reminder. Runs in the executor."""
        due, all_day = _as_due(item.due)
        self._service().create(
            list_id=self._list_id,
            title=item.summary or "",
            desc=item.description or "",
            due_date=due,
            all_day=all_day,
        )

    def _update(self, item: TodoItem) -> None:
        """Apply an update. Runs in the executor."""
        service = self._service()
        reminder = service.get(item.uid)

        if reminder.title == UNDECODED_TITLE:
            # Writing this back would destroy the reminder's real title and
            # notes, so refuse rather than silently corrupting the reminder.
            raise HomeAssistantError(
                "This reminder's title could not be decrypted, so it cannot be "
                "updated. Approve access on one of your Apple devices."
            )

        if item.summary is not None:
            reminder.title = item.summary
        reminder.desc = item.description or ""
        reminder.due_date, reminder.all_day = _as_due(item.due)
        if item.status is not None:
            reminder.completed = item.status == TodoItemStatus.COMPLETED

        service.update(reminder)

    def _delete(self, uids: list[str]) -> None:
        """Delete reminders. Runs in the executor."""
        service = self._service()
        for uid in uids:
            service.delete(service.get(uid))

    async def _async_call(self, func, *args, **kwargs) -> None:
        """Run a blocking call and refresh the list afterwards."""
        try:
            await self.hass.async_add_executor_job(lambda: func(*args, **kwargs))
        except REMINDERS_ERRORS as err:
            raise HomeAssistantError(f"Error updating reminders: {err}") from err
        finally:
            # A batch that failed part of the way through still changed things
            # in iCloud, so refresh either way rather than showing reminders
            # that are already gone until the next poll.
            await self.coordinator.async_request_refresh()


def _as_due(due: date | datetime | None) -> tuple[datetime | None, bool]:
    """Return the due value as ``(datetime, all_day)``.

    ``TodoItem.due`` is a plain ``date`` for an all-day item, but pyicloud
    reads ``tzinfo`` and ``timestamp()`` off whatever it is given, so a date
    has to be widened before it reaches the library.
    """
    if due is None:
        return None, False
    if isinstance(due, datetime):
        return due, False
    return datetime(due.year, due.month, due.day), True


def _ordered(reminders: list[IcloudReminder]) -> list[IcloudReminder]:
    """Return the reminders with each subtask placed after its parent.

    Home Assistant renders a flat list in the order given, and iCloud does not
    guarantee that a subtask follows the reminder it belongs to, so putting it
    there keeps the list reading the way Reminders shows it on iOS. Nesting can
    be deeper than one level, so descendants are emitted recursively.
    """
    uids = {reminder.uid for reminder in reminders}
    children: dict[str, list[IcloudReminder]] = {}
    roots: list[IcloudReminder] = []
    for reminder in reminders:
        # A parent outside this list is no anchor to sort against, so treat the
        # subtask as a root here rather than dropping it. Its parent may well
        # be a reminder in another list.
        if reminder.parent_uid is not None and reminder.parent_uid in uids:
            children.setdefault(reminder.parent_uid, []).append(reminder)
        else:
            roots.append(reminder)

    ordered: list[IcloudReminder] = []

    def _emit(reminder: IcloudReminder) -> None:
        ordered.append(reminder)
        for child in children.pop(reminder.uid, ()):
            _emit(child)

    for reminder in roots:
        _emit(reminder)

    # Anything still here is part of a parent cycle, which iCloud should never
    # return. Pop the whole group before emitting, so the loop terminates.
    while children:
        for orphan in children.pop(next(iter(children))):
            _emit(orphan)

    return ordered


def _as_todo_item(reminder: IcloudReminder) -> TodoItem:
    """Convert a reminder into a to-do item."""
    return TodoItem(
        uid=reminder.uid,
        summary=reminder.summary,
        description=reminder.description,
        due=reminder.due,
        completed=reminder.completed_at if reminder.completed else None,
        status=(
            TodoItemStatus.COMPLETED
            if reminder.completed
            else TodoItemStatus.NEEDS_ACTION
        ),
    )
