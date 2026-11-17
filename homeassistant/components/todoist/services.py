"""Services for Todoist."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime
from enum import StrEnum
import logging
from typing import Any
import uuid

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DUE_DATE_VALID_LANGS
from .coordinator import TodoistConfigEntry, TodoistCoordinator, flatten_async_pages

_LOGGER = logging.getLogger(__name__)


class TodoistService(StrEnum):
    """Store keys for Todoist services."""

    NEW_TASK = "new_task"


class TodoistServiceArgument(StrEnum):
    """Store keys for Todoist service arguments."""

    CONTENT = "content"
    DESCRIPTION = "description"
    PROJECT = "project"
    SECTION = "section"
    LABELS = "labels"
    ASSIGNEE = "assignee"
    PRIORITY = "priority"
    DUE_DATE_STRING = "due_date_string"
    DUE_DATE_LANG = "due_date_lang"
    DUE_DATE = "due_date"
    REMINDER_DATE_STRING = "reminder_date_string"
    REMINDER_DATE_LANG = "reminder_date_lang"
    REMINDER_DATE = "reminder_date"


NEW_TASK_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(TodoistServiceArgument.CONTENT): cv.string,
        probatio.Optional(TodoistServiceArgument.DESCRIPTION): cv.string,
        probatio.Optional(
            TodoistServiceArgument.PROJECT, default="inbox"
        ): probatio.All(cv.string, probatio.Lower),
        probatio.Optional(TodoistServiceArgument.SECTION): probatio.Any(
            probatio.All(cv.string, probatio.Lower), None
        ),
        probatio.Optional(TodoistServiceArgument.LABELS): cv.ensure_list_csv,
        probatio.Optional(TodoistServiceArgument.ASSIGNEE): cv.string,
        probatio.Optional(TodoistServiceArgument.PRIORITY): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=4)
        ),
        probatio.Exclusive(
            TodoistServiceArgument.DUE_DATE_STRING, "due_date"
        ): cv.string,
        probatio.Optional(TodoistServiceArgument.DUE_DATE_LANG): probatio.All(
            cv.string, probatio.In(DUE_DATE_VALID_LANGS)
        ),
        probatio.Exclusive(TodoistServiceArgument.DUE_DATE, "due_date"): cv.string,
        probatio.Exclusive(
            TodoistServiceArgument.REMINDER_DATE_STRING, "reminder_date"
        ): cv.string,
        probatio.Optional(TodoistServiceArgument.REMINDER_DATE_LANG): probatio.All(
            cv.string, probatio.In(DUE_DATE_VALID_LANGS)
        ),
        probatio.Exclusive(
            TodoistServiceArgument.REMINDER_DATE, "reminder_date"
        ): cv.string,
    }
)


def _async_get_coordinator(hass: HomeAssistant) -> TodoistCoordinator:
    """Return a coordinator to service the request.

    Coordinators created by the legacy YAML calendar platform have no config
    entry, so they are stored in hass.data and take precedence. Otherwise fall
    back to the single loaded config entry.
    """
    if coordinators := hass.data.get(DOMAIN):
        return coordinators[0]
    entry: TodoistConfigEntry = service.async_get_config_entry(hass, DOMAIN, None)
    return entry.runtime_data


async def handle_new_task(call: ServiceCall) -> None:
    """Call when a user creates a new Todoist Task from Home Assistant."""
    coordinator = _async_get_coordinator(call.hass)
    project_name = call.data[TodoistServiceArgument.PROJECT]
    projects = await coordinator.async_get_projects()
    project_id: str | None = None
    for project in projects:
        if project_name == project.name.lower():
            project_id = project.id
            break
    if project_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="project_invalid",
            translation_placeholders={
                "project": project_name,
            },
        )

    # Optional section within project. An explicit `None` is accepted and
    # ignored so templated service calls can omit the section conditionally.
    section_id: str | None = None
    if section_name := call.data.get(TodoistServiceArgument.SECTION):
        sections = await coordinator.async_get_sections(project_id)
        for section in sections:
            if section_name == section.name.lower():
                section_id = section.id
                break
        if section_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="section_invalid",
                translation_placeholders={
                    "section": section_name,
                    "project": project_name,
                },
            )

    # Create the task
    content = call.data[TodoistServiceArgument.CONTENT]
    data: dict[str, Any] = {"project_id": project_id}

    if description := call.data.get(TodoistServiceArgument.DESCRIPTION):
        data["description"] = description

    if section_id is not None:
        data["section_id"] = section_id

    if task_labels := call.data.get(TodoistServiceArgument.LABELS):
        data["labels"] = task_labels

    if TodoistServiceArgument.ASSIGNEE in call.data:
        collaborators_result = await coordinator.api.get_collaborators(project_id)
        all_collaborators = await flatten_async_pages(collaborators_result)
        collaborator_id_lookup = {
            collab.name.lower(): collab.id for collab in all_collaborators
        }
        task_assignee = call.data[TodoistServiceArgument.ASSIGNEE].lower()
        if task_assignee in collaborator_id_lookup:
            data["assignee_id"] = collaborator_id_lookup[task_assignee]
        else:
            raise ValueError(
                f"User is not part of the shared project. user: {task_assignee}"
            )

    if TodoistServiceArgument.PRIORITY in call.data:
        data["priority"] = call.data[TodoistServiceArgument.PRIORITY]

    if TodoistServiceArgument.DUE_DATE_STRING in call.data:
        data["due_string"] = call.data[TodoistServiceArgument.DUE_DATE_STRING]

    if TodoistServiceArgument.DUE_DATE_LANG in call.data:
        data["due_lang"] = call.data[TodoistServiceArgument.DUE_DATE_LANG]

    if TodoistServiceArgument.DUE_DATE in call.data:
        due_date = dt_util.parse_datetime(call.data[TodoistServiceArgument.DUE_DATE])
        if due_date is None:
            due = dt_util.parse_date(call.data[TodoistServiceArgument.DUE_DATE])
            if due is None:
                raise ValueError(
                    f"Invalid due_date: {call.data[TodoistServiceArgument.DUE_DATE]}"
                )
            due_date = datetime(due.year, due.month, due.day)
        # Pass the datetime object directly - the library handles formatting
        data["due_datetime"] = dt_util.as_utc(due_date)

    api_task = await coordinator.api.add_task(content, **data)
    await coordinator.async_refresh()

    # The REST API doesn't support reminders, so we use the Sync API directly
    # to maintain functional parity with the component.
    # https://developer.todoist.com/api/v1/#tag/Sync/Reminders/Add-a-reminder
    _reminder_due: dict = {}
    if TodoistServiceArgument.REMINDER_DATE_STRING in call.data:
        _reminder_due["string"] = call.data[TodoistServiceArgument.REMINDER_DATE_STRING]

    if TodoistServiceArgument.REMINDER_DATE_LANG in call.data:
        _reminder_due["lang"] = call.data[TodoistServiceArgument.REMINDER_DATE_LANG]

    if TodoistServiceArgument.REMINDER_DATE in call.data:
        reminder_date = dt_util.parse_datetime(
            call.data[TodoistServiceArgument.REMINDER_DATE]
        )
        if reminder_date is None:
            reminder = dt_util.parse_date(
                call.data[TodoistServiceArgument.REMINDER_DATE]
            )
            if reminder is None:
                raise ValueError(
                    f"Invalid reminder_date: {call.data[TodoistServiceArgument.REMINDER_DATE]}"
                )
            reminder_date = datetime(reminder.year, reminder.month, reminder.day)
        # Format it in the manner Todoist expects (UTC with Z suffix)
        reminder_date = dt_util.as_utc(reminder_date)
        date_format = "%Y-%m-%dT%H:%M:%S.000000Z"
        _reminder_due["date"] = datetime.strftime(reminder_date, date_format)

    if _reminder_due:
        sync_url = "https://api.todoist.com/api/v1/sync"
        reminder_data = {
            "commands": [
                {
                    "type": "reminder_add",
                    "temp_id": str(uuid.uuid1()),
                    "uuid": str(uuid.uuid1()),
                    "args": {
                        "item_id": api_task.id,
                        "type": "absolute",
                        "due": _reminder_due,
                    },
                }
            ]
        }
        headers = {
            "Authorization": f"Bearer {coordinator.token}",
            "Content-Type": "application/json",
        }
        await async_get_clientsession(call.hass).post(
            sync_url, headers=headers, json=reminder_data
        )

    _LOGGER.debug("Created Todoist task: %s", call.data[TodoistServiceArgument.CONTENT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN, TodoistService.NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )
