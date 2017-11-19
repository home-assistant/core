"""
Support for Todoist task management (https://todoist.com).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar.todoist/
"""


from datetime import datetime
from datetime import timedelta
import logging
import os

import asyncio

import voluptuous as vol

from homeassistant.components.calendar import (
    Calendar, CalendarEvent, PLATFORM_SCHEMA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_ID, CONF_NAME, CONF_TOKEN)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt
from homeassistant.util import Throttle

REQUIREMENTS = ['todoist-python==7.0.17']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'todoist'

# Calendar Platform: Does this calendar event last all day?
ALL_DAY = 'all_day'
# Attribute: All tasks in this project
ALL_TASKS = 'all_tasks'
# Todoist API: "Completed" flag -- 1 if complete, else 0
CHECKED = 'checked'
# Attribute: Is this task complete?
COMPLETED = 'completed'
# Todoist API: What is this task about?
# Service Call: What is this task about?
CONTENT = 'content'
# Calendar Platform: Get a calendar event's description
DESCRIPTION = 'description'
# Calendar Platform: Used in the '_get_date()' method
DATETIME = 'dateTime'
# Attribute: When is this task due?
# Service Call: When is this task due?
DUE_DATE = 'due_date'
# Todoist API: Look up a task's due date
DUE_DATE_UTC = 'due_date_utc'
# Attribute: Is this task due today?
DUE_TODAY = 'due_today'
# Calendar Platform: When a calendar event ends
END = 'end'
# Todoist API: Look up a Project/Label/Task ID
ID = 'id'
# Todoist API: Fetch all labels
# Service Call: What are the labels attached to this task?
LABELS = 'labels'
# Todoist API: "Name" value
NAME = 'name'
# Attribute: Is this task overdue?
OVERDUE = 'overdue'
# Attribute: What is this task's priority?
# Todoist API: Get a task's priority
# Service Call: What is this task's priority?
PRIORITY = 'priority'
# Todoist API: Look up the Project ID a Task belongs to
PROJECT_ID = 'project_id'
# Service Call: What Project do you want a Task added to?
PROJECT_NAME = 'project'
# Todoist API: Fetch all Projects
PROJECTS = 'projects'
# Calendar Platform: When does a calendar event start?
START = 'start'
# Calendar Platform: What is the next calendar event about?
SUMMARY = 'summary'
# Todoist API: Fetch all Tasks
TASKS = 'items'

SERVICE_NEW_TASK = 'new_task'
NEW_TASK_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONTENT): cv.string,
    vol.Optional(PROJECT_NAME, default='inbox'): vol.All(cv.string, vol.Lower),
    vol.Optional(LABELS): cv.ensure_list_csv,
    vol.Optional(PRIORITY): vol.All(vol.Coerce(int),
                                    vol.Range(min=1, max=4)),
    vol.Optional(DUE_DATE): cv.string
})

CONF_EXTRA_PROJECTS = 'custom_projects'
CONF_PROJECT_DUE_DATE = 'due_date_days'
CONF_PROJECT_WHITELIST = 'include_projects'
CONF_PROJECT_LABEL_WHITELIST = 'labels'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_EXTRA_PROJECTS, default=[]):
        vol.All(cv.ensure_list, vol.Schema([
            vol.Schema({
                vol.Required(CONF_NAME): cv.string,
                vol.Optional(CONF_PROJECT_DUE_DATE): vol.Coerce(int),
                vol.Optional(CONF_PROJECT_WHITELIST, default=[]):
                    vol.All(cv.ensure_list, [vol.All(cv.string, vol.Lower)]),
                vol.Optional(CONF_PROJECT_LABEL_WHITELIST, default=[]):
                    vol.All(cv.ensure_list, [vol.All(cv.string, vol.Lower)])
            })
        ]))
})

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the calendar platform for event devices."""
    # Check token:
    token = config.get(CONF_TOKEN)

    # Look up IDs based on (lowercase) names.
    project_id_lookup = {}
    label_id_lookup = {}

    from todoist.api import TodoistAPI
    api = TodoistAPI(token)
    api.sync()

    # Setup devices:
    # Grab all projects.
    projects = api.state[PROJECTS]

    # Grab all labels
    labels = api.state[LABELS]

    # Add all Todoist-defined projects.
    project_devices = []
    for project in projects:
        # Project is an object, not a dict!
        # Because of that, we convert what we need to a dict.
        project_data = {
            CONF_NAME: project[NAME],
            CONF_ID: project[ID]
        }

        project_devices.append(TodoistCalendar(api, project_data, labels))

        # Cache the names so we can easily look up name->ID.
        project_id_lookup[project[NAME].lower()] = project[ID]

    # Cache all label names
    for label in labels:
        label_id_lookup[label[NAME].lower()] = label[ID]

    # Check config for more projects.
    extra_projects = config.get(CONF_EXTRA_PROJECTS)
    for project in extra_projects:
        # Special filter: By date
        project_due_date = project.get(CONF_PROJECT_DUE_DATE)

        # Special filter: By label
        project_label_filter = project.get(CONF_PROJECT_LABEL_WHITELIST)

        # Special filter: By name
        # Names must be converted into IDs.
        project_name_filter = project.get(CONF_PROJECT_WHITELIST)
        project_id_filter = [
            project_id_lookup[project_name.lower()]
            for project_name in project_name_filter]

        project_devices.append(TodoistCalendar(api,
                               project, labels, project_due_date,
                               project_label_filter, project_id_filter))

    add_devices(project_devices)

    # Services:
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def handle_new_task(call):
        """Called when a user creates a new Todoist Task from HASS."""
        project_name = call.data[PROJECT_NAME]
        project_id = project_id_lookup[project_name]

        # Create the task
        item = api.items.add(call.data[CONTENT], project_id)

        if LABELS in call.data:
            task_labels = call.data[LABELS]
            label_ids = [
                label_id_lookup[label.lower()]
                for label in task_labels]
            item.update(labels=label_ids)

        if PRIORITY in call.data:
            item.update(priority=call.data[PRIORITY])

        if DUE_DATE in call.data:
            due_date = dt.parse_datetime(call.data[DUE_DATE])
            if due_date is None:
                due = dt.parse_date(call.data[DUE_DATE])
                due_date = datetime(due.year, due.month, due.day)
            # Format it in the manner Todoist expects
            due_date = dt.as_utc(due_date)
            date_format = '%Y-%m-%dT%H:%M'
            due_date = datetime.strftime(due_date, date_format)
            item.update(due_date_utc=due_date)
        # Commit changes
        api.commit()
        _LOGGER.debug("Created Todoist task: %s", call.data[CONTENT])

    hass.services.register(DOMAIN, SERVICE_NEW_TASK, handle_new_task,
                           descriptions[DOMAIN][SERVICE_NEW_TASK],
                           schema=NEW_TASK_SERVICE_SCHEMA)


class TodoistCalendar(Calendar):
    """Entity for Todoist Calendars."""

    def __init__(self, api, project, labels, due_date=None,
                 whitelisted_labels=None, whitelisted_projects=None):
        """Initialze Todoist Calendar entity."""
        self._api = api
        self._events = []
        self._name = project.get(CONF_NAME)
        self._id = project.get(CONF_ID)
        self._next_event = None
        self._labels = labels

        if due_date is not None:
            # TODO: Set to end of day?
            self._due_date = dt.utcnow() + timedelta(days=due_date)
        else:
            self._due_date = None

        if whitelisted_labels is not None:
            self._label_whitelist = whitelisted_labels
        else:
            self._label_whitelist = []

        # This project includes only projects with these names.
        if whitelisted_projects is not None:
            self._project_id_whitelist = whitelisted_projects
        else:
            self._project_id_whitelist = []

        self.refresh_events()

        self._next_event = self.update_next_event()

    @property
    def name(self):
        """Return the name of the calendar."""
        return self._name

    @property
    def next_event(self):
        """Return the next occuring event."""
        return self._next_event

    @asyncio.coroutine
    def async_get_events(self):
        """Return a list of events."""
        return self._events

    @asyncio.coroutine
    def async_update(self):
        """Update Calendar."""
        self.refresh_events()

        self._next_event = self.update_next_event()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_events(self):
        """Update list of event."""
        tasks = []
        if self._id is None:
            tasks = [task for task in self._api.state[TASKS]
                     if not self._project_id_whitelist or
                     task[PROJECT_ID] in self._project_id_whitelist]
        else:
            tasks = self._api.projects.get_data(self._id)[TASKS]

        for task in tasks:
            task_labels = [label[NAME].lower() for label in self._labels
                           if label[ID] in task[LABELS]]

            event = TodoistCalendarEvent(task, task_labels)

            if self._due_date is not None:
                if event.end is None:
                    continue

                if event.end > self._due_date:
                    # This task is out of range of our due date
                    # it shouldn't be included
                    continue

            if self._label_whitelist and (
                not any(label in task_labels
                        for label in self._label_whitelist)):
                # We're not on the whitelist, return invalid task.
                continue

            self._events.append(event)

    def update_next_event(self):
        """
        Search through a list of events for the "best" next event to select.

        The "best" event is determined by the following criteria:
          * A proposed event must not be completed
          * A proposed event must have a end date (otherwise we go with
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
        event = None
        for proposed_event in self._events:
            if event is None:
                event = proposed_event
                continue
            if proposed_event._task_info[CHECKED]:
                # Event is complete!
                continue
            if proposed_event.end is None:
                # No end time:
                if event.end is None and (
                        proposed_event._task_info[PRIORITY] >
                        event._task_info[PRIORITY]):
                    # They also have no end time,
                    # but we have a higher priority.
                    event = proposed_event
                    continue
                else:
                    continue
            elif event.end is None:
                # We have an end time, they do not.
                event = proposed_event
                continue
            if proposed_event.end.date() > event.end.date():
                # Event is too late.
                continue
            elif proposed_event.end.date() < event.end.date():
                # Event is earlier than current, select it.
                event = proposed_event
                continue
            else:
                if (proposed_event._task_info[PRIORITY] >
                   event._task_info[PRIORITY]):
                    # Proposed event has a higher priority.
                    event = proposed_event
                    continue
                elif (proposed_event._task_info[PRIORITY] ==
                      event._task_info[PRIORITY]) and (
                        proposed_event.end < event.end):
                    event = proposed_event
                    continue
        return event


class TodoistCalendarEvent(CalendarEvent):
    """class for creating todoist events."""

    def __init__(self, task, task_labels):
        """Initialize todoist event."""
        self._message = task[CONTENT]
        self._start = dt.utcnow()
        self._labels = task_labels

        # TODO: Handle tasks without due date
        if task[DUE_DATE_UTC] is not None:
            self._end = self.convertDatetime(task[DUE_DATE_UTC])
        else:
            self._end = None

        self._task_info = task

        # TODO: Add additional properties: labels, overdue, all_day, ...

    def convertDatetime(self, dateString):
        """Convert dateTime returned from Todoist."""
        return datetime.strptime(dateString, '%a %d %b %Y %H:%M:%S %z')

    @property
    def start(self):
        """Return start time set on the event."""
        return self._start

    @property
    def end(self):
        """Return end time set on the event."""
        return self._end

    @property
    def message(self):
        """Return text set on the event."""
        return self._message

    @property
    def labels(self):
        """Return labels set on the event."""
        return self._labels
