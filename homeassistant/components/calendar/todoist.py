"""
Support for Todoist task management (https://todoist.com).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar.todoist/
"""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.calendar import (
    DOMAIN, PLATFORM_SCHEMA, CalendarEventDevice)
from homeassistant.components.google import CONF_DEVICE_ID
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import Throttle, dt

REQUIREMENTS = ['todoist-python==7.0.17']

_LOGGER = logging.getLogger(__name__)

CONF_EXTRA_PROJECTS = 'custom_projects'
CONF_PROJECT_DUE_DATE = 'due_date_days'
CONF_PROJECT_LABEL_WHITELIST = 'labels'
CONF_PROJECT_WHITELIST = 'include_projects'

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
# Service Call: When is this task due (in natural language)?
DUE_DATE_STRING = 'due_date_string'
# Service Call: The language of DUE_DATE_STRING
DUE_DATE_LANG = 'due_date_lang'
# Service Call: The available options of DUE_DATE_LANG
DUE_DATE_VALID_LANGS = ['en', 'da', 'pl', 'zh', 'ko', 'de',
                        'pt', 'ja', 'it', 'fr', 'sv', 'ru',
                        'es', 'nl']
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

SERVICE_NEW_TASK = 'todoist_new_task'

NEW_TASK_SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONTENT): cv.string,
    vol.Optional(PROJECT_NAME, default='inbox'): vol.All(cv.string, vol.Lower),
    vol.Optional(LABELS): cv.ensure_list_csv,
    vol.Optional(PRIORITY): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),

    vol.Exclusive(DUE_DATE_STRING, 'due_date'): cv.string,
    vol.Optional(DUE_DATE_LANG):
        vol.All(cv.string, vol.In(DUE_DATE_VALID_LANGS)),
    vol.Exclusive(DUE_DATE, 'due_date'): cv.string,
})

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Todoist platform."""
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
        project_devices.append(
            TodoistProjectDevice(hass, project_data, labels, api)
        )
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

        # Create the custom project and add it to the devices array.
        project_devices.append(
            TodoistProjectDevice(
                hass, project, labels, api, project_due_date,
                project_label_filter, project_id_filter
            )
        )

    add_entities(project_devices)

    def handle_new_task(call):
        """Call when a user creates a new Todoist Task from HASS."""
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

        if DUE_DATE_STRING in call.data:
            item.update(date_string=call.data[DUE_DATE_STRING])

        if DUE_DATE_LANG in call.data:
            item.update(date_lang=call.data[DUE_DATE_LANG])

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
                           schema=NEW_TASK_SERVICE_SCHEMA)


class TodoistProjectDevice(CalendarEventDevice):
    """A device for getting the next Task from a Todoist Project."""

    def __init__(self, hass, data, labels, token,
                 latest_task_due_date=None, whitelisted_labels=None,
                 whitelisted_projects=None):
        """Create the Todoist Calendar Event Device."""
        self.data = TodoistProjectData(
            data, labels, token, latest_task_due_date,
            whitelisted_labels, whitelisted_projects
        )

        # Set up the calendar side of things
        calendar_format = {
            CONF_NAME: data[CONF_NAME],
            # Set Entity ID to use the name so we can identify calendars
            CONF_DEVICE_ID: data[CONF_NAME]
        }

        super().__init__(hass, calendar_format)

    def update(self):
        """Update all Todoist Calendars."""
        # Set basic calendar data
        super().update()

        # Set Todoist-specific data that can't easily be grabbed
        self._cal_data[ALL_TASKS] = [
            task[SUMMARY] for task in self.data.all_project_tasks]

    def cleanup(self):
        """Clean up all calendar data."""
        super().cleanup()
        self._cal_data[ALL_TASKS] = []

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return {}

        attributes = super().device_state_attributes

        # Add additional attributes.
        attributes[DUE_TODAY] = self.data.event[DUE_TODAY]
        attributes[OVERDUE] = self.data.event[OVERDUE]
        attributes[ALL_TASKS] = self._cal_data[ALL_TASKS]
        attributes[PRIORITY] = self.data.event[PRIORITY]
        attributes[LABELS] = self.data.event[LABELS]

        return attributes


class TodoistProjectData:
    """
    Class used by the Task Device service object to hold all Todoist Tasks.

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
    as any updates to current projects/tasks. This is throttled to every
    MIN_TIME_BETWEEN_UPDATES minutes.
    """

    def __init__(self, project_data, labels, api,
                 latest_task_due_date=None, whitelisted_labels=None,
                 whitelisted_projects=None):
        """Initialize a Todoist Project."""
        self.event = None

        self._api = api
        self._name = project_data.get(CONF_NAME)
        # If no ID is defined, fetch all tasks.
        self._id = project_data.get(CONF_ID)

        # All labels the user has defined, for easy lookup.
        self._labels = labels
        # Not tracked: order, indent, comment_count.

        self.all_project_tasks = []

        # The latest date a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        if latest_task_due_date is not None:
            self._latest_due_date = dt.utcnow() + timedelta(
                days=latest_task_due_date)
        else:
            self._latest_due_date = None

        # Only tasks with one of these labels will be included.
        if whitelisted_labels is not None:
            self._label_whitelist = whitelisted_labels
        else:
            self._label_whitelist = []

        # This project includes only projects with these names.
        if whitelisted_projects is not None:
            self._project_id_whitelist = whitelisted_projects
        else:
            self._project_id_whitelist = []

    def create_todoist_task(self, data):
        """
        Create a dictionary based on a Task passed from the Todoist API.

        Will return 'None' if the task is to be filtered out.
        """
        task = {}
        # Fields are required to be in all returned task objects.
        task[SUMMARY] = data[CONTENT]
        task[COMPLETED] = data[CHECKED] == 1
        task[PRIORITY] = data[PRIORITY]
        task[DESCRIPTION] = 'https://todoist.com/showTask?id={}'.format(
            data[ID])

        # All task Labels (optional parameter).
        task[LABELS] = [
            label[NAME].lower() for label in self._labels
            if label[ID] in data[LABELS]]

        if self._label_whitelist and (
                not any(label in task[LABELS]
                        for label in self._label_whitelist)):
            # We're not on the whitelist, return invalid task.
            return None

        # Due dates (optional parameter).
        # The due date is the END date -- the task cannot be completed
        # past this time.
        # That means that the START date is the earliest time one can
        # complete the task.
        # Generally speaking, that means right now.
        task[START] = dt.utcnow()
        if data[DUE_DATE_UTC] is not None:
            due_date = data[DUE_DATE_UTC]

            # Due dates are represented in RFC3339 format, in UTC.
            # Home Assistant exclusively uses UTC, so it'll
            # handle the conversion.
            time_format = '%a %d %b %Y %H:%M:%S %z'
            # HASS' built-in parse time function doesn't like
            # Todoist's time format; strptime has to be used.
            task[END] = datetime.strptime(due_date, time_format)

            if self._latest_due_date is not None and (
                    task[END] > self._latest_due_date):
                # This task is out of range of our due date;
                # it shouldn't be counted.
                return None

            task[DUE_TODAY] = task[END].date() == datetime.today().date()

            # Special case: Task is overdue.
            if task[END] <= task[START]:
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
            if self._latest_due_date is not None:
                return None

            # Define values for tasks without due dates
            task[END] = None
            task[ALL_DAY] = True
            task[DUE_TODAY] = False
            task[OVERDUE] = False

        # Not tracked: id, comments, project_id order, indent, recurring.
        return task

    @staticmethod
    def select_best_task(project_tasks):
        """
        Search through a list of events for the "best" event to select.

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
                if event[END] is None and (
                        proposed_event[PRIORITY] < event[PRIORITY]):
                    # They also have no end time,
                    # but we have a higher priority.
                    event = proposed_event
                    continue
                else:
                    continue
            elif event[END] is None:
                # We have an end time, they do not.
                event = proposed_event
                continue
            if proposed_event[END].date() > event[END].date():
                # Event is too late.
                continue
            elif proposed_event[END].date() < event[END].date():
                # Event is earlier than current, select it.
                event = proposed_event
                continue
            else:
                if proposed_event[PRIORITY] > event[PRIORITY]:
                    # Proposed event has a higher priority.
                    event = proposed_event
                    continue
                elif proposed_event[PRIORITY] == event[PRIORITY] and (
                        proposed_event[END] < event[END]):
                    event = proposed_event
                    continue
        return event

    async def async_get_events(self, hass, start_date, end_date):
        """Get all tasks in a specific time frame."""
        if self._id is None:
            project_task_data = [
                task for task in self._api.state[TASKS]
                if not self._project_id_whitelist or
                task[PROJECT_ID] in self._project_id_whitelist]
        else:
            project_task_data = self._api.projects.get_data(self._id)[TASKS]

        events = []
        time_format = '%a %d %b %Y %H:%M:%S %z'
        for task in project_task_data:
            due_date = datetime.strptime(task['due_date_utc'], time_format)
            if start_date < due_date < end_date:
                event = {
                    'uid': task['id'],
                    'title': task['content'],
                    'start': due_date.isoformat(),
                    'end': due_date.isoformat(),
                    'allDay': True,
                }
                events.append(event)
        return events

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        if self._id is None:
            project_task_data = [
                task for task in self._api.state[TASKS]
                if not self._project_id_whitelist or
                task[PROJECT_ID] in self._project_id_whitelist]
        else:
            project_task_data = self._api.projects.get_data(self._id)[TASKS]

        # If we have no data, we can just return right away.
        if not project_task_data:
            self.event = None
            return True

        # Keep an updated list of all tasks in this project.
        project_tasks = []

        for task in project_task_data:
            todoist_task = self.create_todoist_task(task)
            if todoist_task is not None:
                # A None task means it is invalid for this project
                project_tasks.append(todoist_task)

        if not project_tasks:
            # We had no valid tasks
            return True

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

        self.event = self.all_project_tasks[0]

        # Convert datetime to a string again
        if self.event is not None:
            if self.event[START] is not None:
                self.event[START] = {
                    DATETIME: self.event[START].strftime(DATE_STR_FORMAT)
                }
            if self.event[END] is not None:
                self.event[END] = {
                    DATETIME: self.event[END].strftime(DATE_STR_FORMAT)
                }
            else:
                # HASS gets cranky if a calendar event never ends
                # Let's set our "due date" to tomorrow
                self.event[END] = {
                    DATETIME: (
                        datetime.utcnow() + timedelta(days=1)
                    ).strftime(DATE_STR_FORMAT)
                }
        _LOGGER.debug("Updated %s", self._name)
        return True
