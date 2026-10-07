"""DataUpdateCoordinator for the Remember The Milk integration."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import override

from aiortm import AioRTMClient, AioRTMError, AuthError

from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LIST_ID, DOMAIN, LOGGER, SUBENTRY_TYPE_LIST

UPDATE_INTERVAL = timedelta(minutes=5)


@dataclass(kw_only=True, frozen=True)
class RtmList:
    """An RTM list with its name and current tasks."""

    name: str
    tasks: dict[str, RtmTask]


@dataclass(kw_only=True, frozen=True)
class RtmTask:
    """An RTM task with its HA representation and note metadata."""

    uid: str
    todo_item: TodoItem
    note_id: int | None


@dataclass(kw_only=True, frozen=True)
class RememberTheMilkData:
    """Runtime data for a Remember The Milk config entry."""

    entity_id: str
    client: AioRTMClient
    coordinator: RtmTodoCoordinator


type RememberTheMilkConfigEntry = ConfigEntry[RememberTheMilkData]


class RtmTodoCoordinator(DataUpdateCoordinator[dict[int, RtmList]]):
    """Coordinator for updating task data from RTM."""

    config_entry: RememberTheMilkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RememberTheMilkConfigEntry,
        client: AioRTMClient,
    ) -> None:
        """Initialize the RTM coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.syncing_subentries = False

    @override
    async def _async_update_data(self) -> dict[int, RtmList]:
        """Fetch lists and tasks from the RTM API and sync subentries."""
        try:
            lists_response, tasks_response = await asyncio.gather(
                self.client.rtm.lists.get_list(),
                self.client.rtm.tasks.get_list(),
            )
        except AuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except AioRTMError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

        result: dict[int, RtmList] = {
            lst.id: RtmList(name=lst.name, tasks={})
            for lst in lists_response.lists
            if not (lst.smart or lst.archived or lst.locked or lst.deleted)
        }
        for task_list in tasks_response.tasks.task_list:
            if task_list.id not in result:
                continue
            for taskseries in task_list.taskseries:
                for task in taskseries.task:
                    if task.deleted is not None:
                        continue
                    uid = f"{task_list.id}_{taskseries.id}_{task.id}"
                    status = (
                        TodoItemStatus.COMPLETED
                        if task.completed is not None
                        else TodoItemStatus.NEEDS_ACTION
                    )
                    due: date | datetime | None = None
                    if task.due is not None:
                        due = task.due if task.has_due_time else task.due.date()
                    description: str | None = None
                    note_id: int | None = None
                    if taskseries.notes:
                        first_note = taskseries.notes[0]
                        description = first_note.body or None
                        note_id = first_note.id
                    result[task_list.id].tasks[uid] = RtmTask(
                        uid=uid,
                        todo_item=TodoItem(
                            uid=uid,
                            summary=taskseries.name,
                            status=status,
                            due=due,
                            description=description,
                        ),
                        note_id=note_id,
                    )
        # Schedule after return so self.data is set before the sync runs.
        # The update listener fired by subentry mutations reads coordinator.data,
        # and eager task start means it can run mid-callback synchronously.
        self.config_entry.async_create_task(
            self.hass, self._async_sync_subentries(result), eager_start=False
        )
        return result

    async def _async_sync_subentries(self, lists: dict[int, RtmList]) -> None:
        """Add, update, or remove list subentries to match the fetched lists."""
        entry = self.config_entry
        existing = {
            subentry.data[CONF_LIST_ID]: subentry
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIST)
        }
        self.syncing_subentries = True
        changed = False
        try:
            for list_id, rtm_list in lists.items():
                subentry = existing.get(list_id)
                if subentry is None:
                    self.hass.config_entries.async_add_subentry(
                        entry,
                        ConfigSubentry(
                            data=MappingProxyType({CONF_LIST_ID: list_id}),
                            subentry_type=SUBENTRY_TYPE_LIST,
                            title=rtm_list.name,
                            unique_id=str(list_id),
                        ),
                    )
                    changed = True
                elif subentry.title != rtm_list.name:
                    self.hass.config_entries.async_update_subentry(
                        entry, subentry, title=rtm_list.name
                    )
                    changed = True
            for list_id, subentry in existing.items():
                if list_id not in lists:
                    self.hass.config_entries.async_remove_subentry(
                        entry, subentry.subentry_id
                    )
                    changed = True
        finally:
            self.syncing_subentries = False
        if changed:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
