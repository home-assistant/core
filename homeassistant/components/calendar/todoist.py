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

from homeassistant.components.calendar import Calendar, CalendarEvent
from homeassistant.components.google import (
    CONF_DEVICE_ID)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_ID, CONF_NAME, CONF_TOKEN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import DATE_STR_FORMAT
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

    from todoist.api import TodoistAPI
    api = TodoistAPI(token)
    api.sync()

    projects = api.state[PROJECTS]

    # TODO: Custom 'project' calendars
    add_devices([TodoistCalendar(hass, api, project)
                 for project in projects])


class TodoistCalendar(Calendar):
    """Entity for Todoist Calendars."""

    def __init__(self, hass, api, project):
        """Initialze Todoist Calendar entity."""
        self._api = api
        self._events = []
        self._name = project[NAME]
        self._id = project[ID]
        self._next_event = None

        self.refresh_events()

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

        # TODO: find next event
        #self._next_event = self.update_next_event()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_events(self):
        """Update list of event."""
        tasks = self._api.projects.get_data(self._id)[TASKS]

        self._events = [TodoistCalendarEvent(task) for task in tasks]

class TodoistCalendarEvent(CalendarEvent):
    """class for creating google events."""

    def __init__(self, task):
        """Initialize google event."""
        _LOGGER.info(task)

        self._message = task.get('content')
        self._start = dt.utcnow()

        # TODO: Handle tasks without due date
        self._end = self.convertDatetime(task.get('due_date_utc'))

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
