"""Support for Todoist task management (https://todoist.com)."""

from datetime import date, datetime, timedelta
import logging
from typing import Any, override

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Label, Project, Task
import voluptuous as vol

from homeassistant.components.calendar import (
    PLATFORM_SCHEMA as CALENDAR_PLATFORM_SCHEMA,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TOKEN, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ALL_DAY,
    ALL_TASKS,
    COMPLETED,
    CONF_EXTRA_PROJECTS,
    CONF_PROJECT_DUE_DATE,
    CONF_PROJECT_LABEL_WHITELIST,
    CONF_PROJECT_WHITELIST,
    DESCRIPTION,
    DUE_TODAY,
    END,
    LABELS,
    OVERDUE,
    PRIORITY,
    START,
    SUMMARY,
)
from .coordinator import TodoistConfigEntry, TodoistCoordinator, flatten_async_pages
from .types import CalData, CustomProject, ProjectData, TodoistEvent
from .util import parse_due_date

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = CALENDAR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_EXTRA_PROJECTS, default=[]): vol.All(
            cv.ensure_list,
            vol.Schema(
                [
                    vol.Schema(
                        {
                            vol.Required(CONF_NAME): cv.string,
                            vol.Optional(CONF_PROJECT_DUE_DATE): vol.Coerce(int),
                            vol.Optional(CONF_PROJECT_WHITELIST, default=[]): vol.All(
                                cv.ensure_list, [vol.All(cv.string, vol.Lower)]
                            ),
                            vol.Optional(
                                CONF_PROJECT_LABEL_WHITELIST, default=[]
                            ): vol.All(cv.ensure_list, [vol.All(cv.string)]),
                        }
                    )
                ]
            ),
        ),
    }
)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TodoistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Todoist calendar platform config entry."""
    coordinator = entry.runtime_data
    projects = await coordinator.async_get_projects()
    labels = await coordinator.async_get_labels()

    entities = []
    for project in projects:
        project_data: ProjectData = {CONF_NAME: project.name, CONF_ID: project.id}
        entities.append(TodoistProjectEntity(coordinator, project_data, labels))

    async_add_entities(entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Todoist platform."""
    token = config[CONF_TOKEN]

    # Look up IDs based on (lowercase) names.
    project_id_lookup = {}

    api = TodoistAPIAsync(token)
    coordinator = TodoistCoordinator(hass, _LOGGER, None, SCAN_INTERVAL, api, token)
    await coordinator.async_refresh()

    async def _shutdown_coordinator(_: Event) -> None:
        await coordinator.async_shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_coordinator)

    # Setup devices:
    # Grab all projects.
    projects_result = await api.get_projects()
    all_projects: list[Project] = await flatten_async_pages(projects_result)

    # Grab all labels
    labels_result = await api.get_labels()
    all_labels: list[Label] = await flatten_async_pages(labels_result)

    # Add all Todoist-defined projects.
    project_devices = []
    for project in all_projects:
        # Project is an object, not a dict!
        # Because of that, we convert what we need to a dict.
        project_data: ProjectData = {CONF_NAME: project.name, CONF_ID: project.id}
        project_devices.append(
            TodoistProjectEntity(coordinator, project_data, all_labels)
        )
        # Cache the names so we can easily look up name->ID.
        project_id_lookup[project.name.lower()] = project.id

    # Check config for more projects.
    extra_projects: list[CustomProject] = config[CONF_EXTRA_PROJECTS]
    for extra_project in extra_projects:
        # Special filter: By date
        project_due_date = extra_project.get(CONF_PROJECT_DUE_DATE)

        # Special filter: By label
        project_label_filter = extra_project[CONF_PROJECT_LABEL_WHITELIST]

        # Special filter: By name
        # Names must be converted into IDs.
        project_name_filter = extra_project[CONF_PROJECT_WHITELIST]
        project_id_filter: list[str] | None = None
        if project_name_filter is not None:
            project_id_filter = [
                project_id_lookup[project_name.lower()]
                for project_name in project_name_filter
            ]

        # Create the custom project and add it to the devices array.
        project_devices.append(
            TodoistProjectEntity(
                coordinator,
                {"id": None, "name": extra_project["name"]},
                all_labels,
                due_date_days=project_due_date,
                whitelisted_labels=project_label_filter,
                whitelisted_projects=project_id_filter,
            )
        )

    async_add_entities(project_devices, update_before_add=True)


class TodoistProjectEntity(CoordinatorEntity[TodoistCoordinator], CalendarEntity):
    """A device for getting the next Task from a Todoist Project."""

    def __init__(
        self,
        coordinator: TodoistCoordinator,
        data: ProjectData,
        labels: list[Label],
        due_date_days: int | None = None,
        whitelisted_labels: list[str] | None = None,
        whitelisted_projects: list[str] | None = None,
    ) -> None:
        """Create the Todoist Calendar Entity."""
        super().__init__(coordinator=coordinator)
        self.data = TodoistProjectData(
            data,
            labels,
            coordinator,
            due_date_days=due_date_days,
            whitelisted_labels=whitelisted_labels,
            whitelisted_projects=whitelisted_projects,
        )
        self._cal_data: CalData = {}
        self._name = data[CONF_NAME]
        self._attr_unique_id = (
            str(data[CONF_ID]) if data.get(CONF_ID) is not None else None
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.data.update()
        super()._handle_coordinator_update()

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self.data.calendar_event

    @property
    @override
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @override
    async def async_update(self) -> None:
        """Update all Todoist Calendars."""
        await super().async_update()
        self.data.update()

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(start_date, end_date)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return None

        return {
            DUE_TODAY: self.data.event[DUE_TODAY],
            OVERDUE: self.data.event[OVERDUE],
            ALL_TASKS: [task[SUMMARY] for task in self.data.all_project_tasks],
            PRIORITY: self.data.event[PRIORITY],
            LABELS: self.data.event[LABELS],
        }


class TodoistProjectData:
    """Class used by the Task Entity service object to hold all Todoist Tasks.

    This is analogous to the GoogleCalendarData found in the Google Calendar
    component.

    Takes an object with a 'name' field and optionally an 'id' field (either
    user-defined or from the Todoist API), a Todoist API token, and an optional
    integer specifying the latest number of days from now a task can be due (7
    means everything due in the next week, 0 means today, etc.).

    This object has an exposed 'event' property (used by the Calendar platform
    to determine the next calendar event) and an exposed 'update' method (used
    by the Calendar platform to poll for new calendar events).

    The 'event' is a representation of a Todoist Task, with defined parameters
    of 'due_today' (is the task due today?), 'all_day' (does the task have a
    due date?), 'task_labels' (all labels assigned to the task), 'message'
    (the content of the task, e.g. 'Fetch Mail'), 'description' (a URL pointing
    to the task on the Todoist website), 'end_time' (what time the event is
    due), 'start_time' (what time this event was last updated), 'overdue' (is
    the task past its due date?), 'priority' (1-4, how important the task is,
    with 4 being the most important), and 'all_tasks' (all tasks in this
    project, sorted by how important they are).

    'offset_reached', 'location', and 'friendly_name' are defined by the
    platform itself, but are not used by this component at all.

    The 'update' method polls the Todoist API for new projects/tasks, as well
    as any updates to current projects/tasks. This occurs every SCAN_INTERVAL minutes.
    """

    def __init__(
        self,
        project_data: ProjectData,
        labels: list[Label],
        coordinator: TodoistCoordinator,
        due_date_days: int | None = None,
        whitelisted_labels: list[str] | None = None,
        whitelisted_projects: list[str] | None = None,
    ) -> None:
        """Initialize a Todoist Project."""
        self.event: TodoistEvent | None = None

        self._coordinator = coordinator
        self._name = project_data[CONF_NAME]
        # If no ID is defined, this is a custom project.
        self._id = project_data.get(CONF_ID)

        # All labels the user has defined, for easy lookup.
        self._labels = labels
        # Not tracked: order, indent, comment_count.

        self.all_project_tasks: list[TodoistEvent] = []

        # The days a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        self._due_date_days: timedelta | None = None
        if due_date_days is not None:
            self._due_date_days = timedelta(days=due_date_days)

        # Only tasks with one of these labels will be included.
        self._label_whitelist: list[str] = []
        if whitelisted_labels is not None:
            self._label_whitelist = whitelisted_labels

        # This project includes only projects with these names.
        self._project_id_whitelist: list[str] = []
        if whitelisted_projects is not None:
            self._project_id_whitelist = whitelisted_projects

    @property
    def calendar_event(self) -> CalendarEvent | None:
        """Return the next upcoming calendar event."""
        if not self.event:
            return None

        start = self.event[START]
        if self.event.get(ALL_DAY) or self.event[END] is None:
            return CalendarEvent(
                summary=self.event[SUMMARY],
                start=start.date(),
                end=start.date() + timedelta(days=1),
            )

        return CalendarEvent(
            summary=self.event[SUMMARY], start=start, end=self.event[END]
        )

    def create_todoist_task(self, data: Task):
        """Create a dictionary based on a Task passed from the Todoist API.

        Will return 'None' if the task is to be filtered out.
        """
        task: TodoistEvent = {
            ALL_DAY: False,
            COMPLETED: data.completed_at is not None,
            DESCRIPTION: f"https://todoist.com/showTask?id={data.id}",
            DUE_TODAY: False,
            END: None,
            LABELS: [],
            OVERDUE: False,
            PRIORITY: data.priority,
            START: dt_util.now(),
            SUMMARY: data.content,
        }

        if (
            self._project_id_whitelist
            and data.project_id not in self._project_id_whitelist
        ):
            # Project isn't in `include_projects` filter.
            return None

        # All task Labels (optional parameter).
        labels = data.labels or []
        task[LABELS] = [label.name for label in self._labels if label.name in labels]
        if self._label_whitelist and (
            not any(label in task[LABELS] for label in self._label_whitelist)
        ):
            # We're not on the whitelist, return invalid task.
            return None

        # Due dates (optional parameter).
        # The due date is the END date -- the task cannot be completed
        # past this time.
        # That means that the START date is the earliest time one can
        # complete the task.
        # Generally speaking, that means right now.
        if data.due is not None:
            due_date = data.due.date
            # The API returns date or datetime objects when deserialized via from_dict()
            if isinstance(due_date, datetime):
                task[END] = dt_util.as_local(due_date)
            elif isinstance(due_date, date):
                task[END] = dt_util.start_of_local_day(due_date)

            if (end_dt := task[END]) is not None:
                if self._due_date_days is not None:
                    # For comparison with now, use datetime

                    if end_dt > dt_util.now() + self._due_date_days:
                        # This task is out of range of our due date;
                        # it shouldn't be counted.
                        return None

                task[DUE_TODAY] = end_dt.date() == dt_util.now().date()

                # Special case: Task is overdue.
                if end_dt <= task[START]:
                    task[OVERDUE] = True
                    # Set end time to the current time plus 1 hour.
                    # We're pretty much guaranteed to update within that 1 hour,
                    # so it should be fine.
                    task[END] = task[START] + timedelta(hours=1)
                else:
                    task[OVERDUE] = False
        else:
            # If we ask for everything due before a certain date, don't count
            # things which have no due dates.
            if self._due_date_days is not None:
                return None

            # Define values for tasks without due dates
            task[END] = None
            task[ALL_DAY] = True
            task[DUE_TODAY] = False
            task[OVERDUE] = False

        # Not tracked: id, comments, project_id order, indent, recurring.
        return task

    @staticmethod
    def select_best_task(project_tasks: list[TodoistEvent]) -> TodoistEvent:
        """Search through a list of events for the "best" event to select.

        The "best" event is determined by the following criteria:
          * A proposed event must not be completed
          * A proposed event must have an end date (otherwise we go with
            the event at index 0, selected above)
          * A proposed event must be on the same day or earlier as our
            current event
          * If a proposed event is an earlier day than what we have so
            far, select it
          * If a proposed event is on the same day as our current event
            and the proposed event has a higher priority than our current
            event, select it
          * If a proposed event is on the same day as our current event,
            has the same priority as our current event, but is due earlier
            in the day, select it
        """
        # Start at the end of the list, so if tasks don't have a due date
        # the newest ones are the most important.

        event = project_tasks[-1]

        for proposed_event in project_tasks:
            if event == proposed_event:
                continue

            if proposed_event[COMPLETED]:
                # Event is complete!
                continue

            if proposed_event[END] is None:
                # No end time:
                if event[END] is None and (proposed_event[PRIORITY] < event[PRIORITY]):
                    # They also have no end time,
                    # but we have a higher priority.
                    event = proposed_event
                continue

            if event[END] is None:
                # We have an end time, they do not.
                event = proposed_event
                continue

            if proposed_event[END].date() > event[END].date():
                # Event is too late.
                continue

            if proposed_event[END].date() < event[END].date():
                # Event is earlier than current, select it.
                event = proposed_event
                continue

            if proposed_event[PRIORITY] > event[PRIORITY]:
                # Proposed event has a higher priority.
                event = proposed_event
                continue

            if proposed_event[PRIORITY] == event[PRIORITY] and (
                event[END] is not None and proposed_event[END] < event[END]
            ):
                event = proposed_event
                continue
        return event

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all tasks in a specific time frame."""
        tasks = self._coordinator.data
        if self._id is None:
            project_task_data = [
                task for task in tasks if self.create_todoist_task(task) is not None
            ]
        else:
            project_task_data = [task for task in tasks if task.project_id == self._id]

        events = []
        for task in project_task_data:
            if task.due is None:
                continue
            start = parse_due_date(task.due)
            if start is None:
                continue
            event = CalendarEvent(
                summary=task.content,
                start=start,
                end=start + timedelta(days=1),
            )
            if (
                event.start_datetime_local is not None
                and event.start_datetime_local >= end_date
            ):
                continue
            if (
                event.end_datetime_local is not None
                and event.end_datetime_local < start_date
            ):
                continue
            events.append(event)
        return events

    def update(self) -> None:
        """Get the latest data."""
        tasks = self._coordinator.data
        if self._id is None:
            project_task_data = [
                task
                for task in tasks
                if not self._project_id_whitelist
                or task.project_id in self._project_id_whitelist
            ]
        else:
            project_task_data = [task for task in tasks if task.project_id == self._id]

        # If we have no data, we can just return right away.
        if not project_task_data:
            _LOGGER.debug("No data for %s", self._name)
            self.event = None
            return

        # Keep an updated list of all tasks in this project.
        project_tasks = []
        for task in project_task_data:
            todoist_task = self.create_todoist_task(task)
            if todoist_task is not None:
                # A None task means it is invalid for this project
                project_tasks.append(todoist_task)

        if not project_tasks:
            # We had no valid tasks
            _LOGGER.debug("No valid tasks for %s", self._name)
            self.event = None
            return

        # Make sure the task collection is reset to prevent an
        # infinite collection repeating the same tasks
        self.all_project_tasks.clear()

        # Organize the best tasks (so users can see all the tasks
        # they have, organized)
        while project_tasks:
            best_task = self.select_best_task(project_tasks)
            _LOGGER.debug("Found Todoist Task: %s", best_task[SUMMARY])
            project_tasks.remove(best_task)
            self.all_project_tasks.append(best_task)

        event = self.all_project_tasks[0]
        if event is None or event[START] is None:
            _LOGGER.debug("No valid event or event start for %s", self._name)
            self.event = None
            return
        self.event = event
        _LOGGER.debug("Updated %s", self._name)
