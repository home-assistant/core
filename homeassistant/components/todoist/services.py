"""Services for Todoist."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime
import logging
from typing import Any
import uuid

import probatio

from homeassistant.components.zone import ATTR_RADIUS, DOMAIN as ZONE_DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    ASSIGNEE,
    CONTENT,
    DESCRIPTION,
    DOMAIN,
    DUE_DATE,
    DUE_DATE_LANG,
    DUE_DATE_STRING,
    DUE_DATE_VALID_LANGS,
    LABELS,
    MAX_REMINDER_RADIUS,
    PRIORITY,
    PROJECT_NAME,
    REMINDER_DATE,
    REMINDER_DATE_LANG,
    REMINDER_DATE_STRING,
    REMINDER_LATITUDE,
    REMINDER_LOCATION_DIRECTION,
    REMINDER_LOCATION_DIRECTION_ENTER,
    REMINDER_LOCATION_NAME,
    REMINDER_LOCATION_VALID_DIRECTIONS,
    REMINDER_LONGITUDE,
    REMINDER_RADIUS,
    REMINDER_ZONE,
    SECTION_NAME,
    SERVICE_NEW_TASK,
)
from .coordinator import TodoistConfigEntry, TodoistCoordinator, flatten_async_pages

_LOGGER = logging.getLogger(__name__)

SYNC_URL = "https://api.todoist.com/api/v1/sync"

# All coordinate fields must be supplied together, and they are mutually
# exclusive with a zone. Using the location name as the anchor of the inclusive
# group means checking it against the zone covers the whole group.
NEW_TASK_SERVICE_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONTENT): cv.string,
            probatio.Optional(DESCRIPTION): cv.string,
            probatio.Optional(PROJECT_NAME, default="inbox"): probatio.All(
                cv.string, probatio.Lower
            ),
            probatio.Optional(SECTION_NAME): probatio.Any(
                probatio.All(cv.string, probatio.Lower), None
            ),
            probatio.Optional(LABELS): cv.ensure_list_csv,
            probatio.Optional(ASSIGNEE): cv.string,
            probatio.Optional(PRIORITY): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=4)
            ),
            probatio.Exclusive(DUE_DATE_STRING, "due_date"): cv.string,
            probatio.Optional(DUE_DATE_LANG): probatio.All(
                cv.string, probatio.In(DUE_DATE_VALID_LANGS)
            ),
            probatio.Exclusive(DUE_DATE, "due_date"): cv.string,
            probatio.Exclusive(REMINDER_DATE_STRING, "reminder_date"): cv.string,
            probatio.Optional(REMINDER_DATE_LANG): probatio.All(
                cv.string, probatio.In(DUE_DATE_VALID_LANGS)
            ),
            probatio.Exclusive(REMINDER_DATE, "reminder_date"): cv.string,
            probatio.Optional(REMINDER_ZONE): cv.entity_domain(ZONE_DOMAIN),
            probatio.Inclusive(REMINDER_LOCATION_NAME, "reminder_location"): cv.string,
            probatio.Inclusive(REMINDER_LATITUDE, "reminder_location"): cv.latitude,
            probatio.Inclusive(REMINDER_LONGITUDE, "reminder_location"): cv.longitude,
            probatio.Inclusive(REMINDER_RADIUS, "reminder_location"): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=MAX_REMINDER_RADIUS)
            ),
            probatio.Optional(
                REMINDER_LOCATION_DIRECTION, default=REMINDER_LOCATION_DIRECTION_ENTER
            ): probatio.In(REMINDER_LOCATION_VALID_DIRECTIONS),
        }
    ),
    probatio.AtMostOne(REMINDER_ZONE, REMINDER_LOCATION_NAME),
)


def _get_reminder_due(call: ServiceCall) -> dict[str, Any]:
    """Return the Sync API due arguments for a time based reminder, if any."""
    reminder_due: dict[str, Any] = {}
    if REMINDER_DATE_STRING in call.data:
        reminder_due["string"] = call.data[REMINDER_DATE_STRING]

    if REMINDER_DATE_LANG in call.data:
        reminder_due["lang"] = call.data[REMINDER_DATE_LANG]

    if REMINDER_DATE in call.data:
        reminder_date = dt_util.parse_datetime(call.data[REMINDER_DATE])
        if reminder_date is None:
            reminder = dt_util.parse_date(call.data[REMINDER_DATE])
            if reminder is None:
                raise ValueError(f"Invalid reminder_date: {call.data[REMINDER_DATE]}")
            reminder_date = datetime(reminder.year, reminder.month, reminder.day)
        # Format it in the manner Todoist expects (UTC with Z suffix)
        reminder_date = dt_util.as_utc(reminder_date)
        date_format = "%Y-%m-%dT%H:%M:%S.000000Z"
        reminder_due["date"] = datetime.strftime(reminder_date, date_format)

    return reminder_due


def _get_reminder_location(call: ServiceCall) -> dict[str, Any] | None:
    """Return the Sync API location arguments for the requested reminder, if any."""
    if zone_entity_id := call.data.get(REMINDER_ZONE):
        if (zone := call.hass.states.get(zone_entity_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="zone_invalid",
                translation_placeholders={"zone": zone_entity_id},
            )
        name = zone.name
        latitude = zone.attributes[ATTR_LATITUDE]
        longitude = zone.attributes[ATTR_LONGITUDE]
        # Zones don't limit their radius, so apply the same bounds as coordinates.
        zone_radius = zone.attributes[ATTR_RADIUS]
        radius = int(zone_radius)
        if not 1 <= radius <= MAX_REMINDER_RADIUS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="zone_radius_invalid",
                translation_placeholders={
                    "zone": zone_entity_id,
                    "radius": f"{zone_radius:g}",
                    "max_radius": str(MAX_REMINDER_RADIUS),
                },
            )
    elif REMINDER_LOCATION_NAME in call.data:
        name = call.data[REMINDER_LOCATION_NAME]
        latitude = call.data[REMINDER_LATITUDE]
        longitude = call.data[REMINDER_LONGITUDE]
        radius = call.data[REMINDER_RADIUS]
    else:
        return None

    return {
        "type": "location",
        "name": name,
        "loc_lat": str(latitude),
        "loc_long": str(longitude),
        "loc_trigger": call.data[REMINDER_LOCATION_DIRECTION],
        "radius": radius,
    }


async def _async_add_reminders(
    hass: HomeAssistant, token: str, reminders: list[dict[str, Any]]
) -> None:
    """Add reminders to a task.

    The REST API doesn't support reminders, so we use the Sync API directly
    to maintain functional parity with the component.
    https://developer.todoist.com/api/v1/#tag/Sync/Reminders/Add-a-reminder
    """
    commands = [
        {
            "type": "reminder_add",
            "temp_id": str(uuid.uuid1()),
            "uuid": str(uuid.uuid1()),
            "args": args,
        }
        for args in reminders
    ]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    await async_get_clientsession(hass).post(
        SYNC_URL, headers=headers, json={"commands": commands}
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
    project_name = call.data[PROJECT_NAME]
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
    if section_name := call.data.get(SECTION_NAME):
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
    content = call.data[CONTENT]
    data: dict[str, Any] = {"project_id": project_id}

    if description := call.data.get(DESCRIPTION):
        data["description"] = description

    if section_id is not None:
        data["section_id"] = section_id

    if task_labels := call.data.get(LABELS):
        data["labels"] = task_labels

    if ASSIGNEE in call.data:
        collaborators_result = await coordinator.api.get_collaborators(project_id)
        all_collaborators = await flatten_async_pages(collaborators_result)
        collaborator_id_lookup = {
            collab.name.lower(): collab.id for collab in all_collaborators
        }
        task_assignee = call.data[ASSIGNEE].lower()
        if task_assignee in collaborator_id_lookup:
            data["assignee_id"] = collaborator_id_lookup[task_assignee]
        else:
            raise ValueError(
                f"User is not part of the shared project. user: {task_assignee}"
            )

    if PRIORITY in call.data:
        data["priority"] = call.data[PRIORITY]

    if DUE_DATE_STRING in call.data:
        data["due_string"] = call.data[DUE_DATE_STRING]

    if DUE_DATE_LANG in call.data:
        data["due_lang"] = call.data[DUE_DATE_LANG]

    if DUE_DATE in call.data:
        due_date = dt_util.parse_datetime(call.data[DUE_DATE])
        if due_date is None:
            due = dt_util.parse_date(call.data[DUE_DATE])
            if due is None:
                raise ValueError(f"Invalid due_date: {call.data[DUE_DATE]}")
            due_date = datetime(due.year, due.month, due.day)
        # Pass the datetime object directly - the library handles formatting
        data["due_datetime"] = dt_util.as_utc(due_date)

    # Resolve reminders first so an invalid one doesn't leave a task behind.
    reminders: list[dict[str, Any]] = []

    if reminder_due := _get_reminder_due(call):
        reminders.append({"type": "absolute", "due": reminder_due})

    if location := _get_reminder_location(call):
        reminders.append(location)

    api_task = await coordinator.api.add_task(content, **data)
    await coordinator.async_refresh()

    if reminders:
        await _async_add_reminders(
            call.hass,
            coordinator.token,
            [{"item_id": api_task.id, **reminder} for reminder in reminders],
        )

    _LOGGER.debug("Created Todoist task: %s", call.data[CONTENT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )
