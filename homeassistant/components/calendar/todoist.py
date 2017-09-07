"""
Support for Todoist task management (https://todoist.com).

Todoist breaks task management down into 2 structures:
* Tasks, which are "things" you can do and can mark as being done
* Projects, which are essentially containers for tasks.

Projects are used to organize and group tasks together as being related.
For example, for a student, one of their classes could be considered a project.
All homework, projects, tests, etc. that are due in that class could get
grouped up into that class' project.

Additionally, you can use labels to group together tasks for easier sorting.
You can tag a task with the "Homework" label, and then later grab all tasks
which have the label "Homework", no matter where they are.

You can additionally give tasks a priority, which in Todoist ranges from 4
(least priority) to 1 (highest priority). Tasks default to 4, generally.

In Home Assistant, each project gets its own calendar. The calendar keeps track
of what your most "important" task in that project is. Usually, it's whatever
task is due first -- if one task is due tomorrow and the next is due next week,
the task due tomorrow would be considered more important.
If two tasks are due on the same day, the task with the higher priority is
considered to be the most important.

If no tasks in a project have a due date, the task with the highest priority
is returned. In the event of a tie, the task which was added most recently
is considered the winner.

You can view all tasks in a project in that project's entity view, meaning
that you can use that data to create template sensors if needed.
The tasks listed in the entity view are sorted from most important to
least important.

Example configuration:
calendar:
  - platform: todoist
    # API token: https://todoist.com/Users/viewPrefs?page=authorizations
    token: !secret todoist_token
    # Optional, allows user to specify their own devices that aren't on
    # the actual Todoist platform
    custom_projects:
      # Return all tasks the user has, no matter where they are
      - name: 'All Projects'
      # Return all tasks due today
      - name: 'Due Today'
        due_date_days: 0
      # Return all tasks due in the next 7 days
      - name: 'Due This Week'
        due_date_days: 7
      # Return all tasks which:
      # * Have a specific label
      # * Are in specific projects
      - name: 'Math Homework'
        labels:
          - Homework
        include_projects:
          - Mathematical Structures II
          - Calculus II
      # All of the above can be mixed-and-matched
      # Everything is optional except for 'name'.
"""

import json
import logging
import uuid
from datetime import datetime
from datetime import timedelta
import os

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.google import (
    CONF_DEVICE_ID, CONF_NAME)
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.components.calendar import CalendarEventDevice
from homeassistant.util import Throttle
from homeassistant.config import load_yaml_config_file

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'todoist'

SERVICE_NEW_TASK = 'new_task'
NEW_TASK_SERVICE_SCHEMA = vol.Schema({
    vol.Required('content'): cv.string,
    vol.Optional('project'): cv.string,
    vol.Optional('labels'): cv.string,
    vol.Optional('priority'): vol.All(vol.Coerce(int),
                                      vol.Range(min=1, max=4)),
    vol.Exclusive('due_date', 'todoist_due'): cv.string,
    vol.Exclusive('due_datetime', 'todoist_due'): cv.datetime,
})

# Your Todoist API token.
# Find yours at https://todoist.com/Users/viewPrefs?page=authorizations.
CONF_API_TOKEN = 'token'
CONF_EXTRA_PROJECTS = 'custom_projects'
CONF_PROJECT_NAME = 'name'
CONF_PROJECT_DUE_DATE = 'due_date_days'
CONF_PROJECT_WHITELIST = 'include_projects'
CONF_PROJECT_LABEL_WHITELIST = 'labels'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_TOKEN): cv.string,
        vol.Optional(CONF_EXTRA_PROJECTS): vol.Schema({
            vol.Required(CONF_PROJECT_NAME): cv.string,
            vol.Optional(CONF_PROJECT_DUE_DATE): vol.Coerce(int),
            vol.Optional(CONF_PROJECT_WHITELIST): cv.ensure_list,
            vol.Optional(CONF_PROJECT_LABEL_WHITELIST): cv.ensure_list
        })
    })
}, extra=vol.ALLOW_EXTRA)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

# Look up IDs based on (lowercase) names.
project_id_lookup = {}  # pylint: disable=C0103
label_id_lookup = {}  # pylint: disable=C0103


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Todoist platform."""
    # Check token:
    token = config.get(CONF_API_TOKEN)
    if token is None or not isinstance(token, str):
        raise ValueError(
            "Invalid Todoist token! Did you add it to your configuration?"
        )

    # Setup devices:
    # Grab all projects.
    projects = requests.get(
        'https://beta.todoist.com/API/v8/projects',
        params={'token': token}
    ).json()

    # Grab all labels.
    labels = requests.get(
        "https://beta.todoist.com/API/v8/labels",
        params={"token": token}
    ).json()

    # Add all Todoist-defined projects.
    project_devices = []
    for project in projects:
        project_devices.append(
            TodoistProjectDevice(hass, project, labels, token)
        )
        # Cache the names so we can easily look up name->ID.
        project_id_lookup[project['name'].lower()] = project['id']

    # Cache all label names
    for label in labels:
        label_id_lookup[label['name'].lower()] = label['id']

    # Check config for more projects.
    extra_projects = config.get(CONF_EXTRA_PROJECTS)
    if extra_projects is not None:
        for project in extra_projects:
            # Special filter: By date
            project_due_date = project.get(CONF_PROJECT_DUE_DATE)

            # Special filter: By label
            project_label_filter = project.get(CONF_PROJECT_LABEL_WHITELIST)

            # Special filter: By name
            # Names must be converted into IDs.
            project_name_filter = project.get(CONF_PROJECT_WHITELIST)
            if project_name_filter is not None and (
                    len(project_name_filter) > 0):
                project_id_filter = []
                for project_name in project_name_filter:
                    project_id_filter.append(
                        project_id_lookup[project_name.lower()]
                    )
            else:
                project_id_filter = None

            # Create the custom project and add it to the devices array.
            project_devices.append(
                TodoistProjectDevice(
                    hass, project, labels, token, project_due_date,
                    project_label_filter, project_id_filter
                )
            )

    add_devices(project_devices)

    # Services:
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def handle_new_task(call):
        """Called when a user creates a new Todoist Task from HASS."""
        task_data = {}
        task_data['content'] = call.data['content']

        if 'project' in call.data:
            project_name = call.data['project'].lower()
            task_data['project_id'] = project_id_lookup[project_name]

        if 'labels' in call.data:
            task_labels = call.data['labels'].split(',')
            task_data['label_ids'] = []
            for label in task_labels:
                task_data['label_ids'].append(
                    label_id_lookup[label.lower()])

        if 'priority' in call.data:
            task_data['priority'] = call.data['priority']

        if 'due_datetime' in call.data:
            task_data['due_datetime'] = call.data['due_datetime']
        elif 'due_date' in call.data:
            task_data['due_date'] = call.data['due_date']

        task_json = json.dumps(task_data)

        # Post it to Todoist
        output = requests.post("https://beta.todoist.com/API/v8/tasks",
                               params={"token": token},
                               data=task_json,
                               headers={
                                   "Content-Type": "application/json",
                                   "X-Request-Id": str(uuid.uuid4()),
                               })
        if output.status_code == 200:
            _LOGGER.info("Successfully posted task to Todoist.")
        else:
            error = "Could not post task to Todoist! "
            error += "Status code: " + str(output.status_code)
            _LOGGER.critical(error)
    hass.services.register(DOMAIN, SERVICE_NEW_TASK, handle_new_task,
                           descriptions[DOMAIN][SERVICE_NEW_TASK],
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
        calendar_format = {}
        calendar_format[CONF_NAME] = data['name']
        calendar_format[CONF_DEVICE_ID] = data['name']

        super().__init__(hass, calendar_format)

    def update(self):
        """Update all Todoist Calendars."""
        # Set basic calendar data
        super().update()

        # Set Todoist-specific data that can't easily be grabbed
        if self.data.event is not None and 'all_day' in self.data.event:
            # This event doesn't have an end time, so we mark it as all day.
            self._cal_data['all_day'] = True

        self._cal_data['all_tasks'] = []
        for task in self.data.all_project_tasks:
            self._cal_data['all_tasks'].append(task['summary'])

    def cleanup(self):
        """Clean up all calendar data."""
        super().cleanup()
        self._cal_data['all_tasks'] = []

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return {}

        attributes = super().device_state_attributes

        # Add additional attributes.
        attributes['due_today'] = self.data.event['due_today']
        attributes['overdue'] = self.data.event['overdue']
        attributes['all_tasks'] = self._cal_data['all_tasks']
        attributes['priority'] = self.data.event['priority']
        attributes['task_comments'] = self.data.event['comments']
        attributes['task_labels'] = self.data.event['labels']

        return attributes


class TodoistProjectData(object):
    """
    Class used by the Task Device service object to hold all Todoist Tasks.

    Takes a JSON representation of the project data (returned from the
    Todoist API), a Todoist API token, and an optional integer specifying the
    latest number of days from now a task can be due (7 means everything due in
    the next week, 0 means today, etc.).
    """

    def __init__(self, project_data, labels, token,
                 latest_task_due_date=None, whitelisted_labels=None,
                 whitelisted_projects=None):
        """Initialize a Todoist Project."""
        self.event = None

        _LOGGER.info("Creating Todoist Project " + str(project_data))

        self._token = token
        self._name = project_data['name']
        # If no ID is defined, fetch all tasks.
        if 'id' in project_data:
            self._id = project_data['id']
        else:
            self._id = None
        # All labels the user has defined, for easy lookup.
        self._labels = labels
        # Not tracked: order, indent, comment_count.

        self.all_project_tasks = []

        # The latest date a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        if latest_task_due_date is not None:
            self._latest_due_date = datetime.now() + timedelta(
                days=latest_task_due_date)
        else:
            self._latest_due_date = None

        # Only tasks with one of these labels will be included.
        if whitelisted_labels is not None:
            self._label_whitelist = whitelisted_labels
        else:
            self._label_whitelist = None

        # This project includes only projects with these names.
        if whitelisted_projects is not None:
            self._project_id_whitelist = whitelisted_projects
        else:
            self._project_id_whitelist = None

    def create_todoist_task(self, data):
        """
        Create a Todoist Task from a given JSON object.

        Will return 'None' if the task is to be filtered out.
        """
        task = {}
        # Fields are required to be in all returned task objects.
        task['summary'] = data['content']
        task['completed'] = data['completed']
        task['priority'] = data['priority']
        task['description'] = data['url']

        # All task Labels (optional parameter).
        task['labels'] = []
        if 'label_ids' in data and len(data['label_ids']) > 0:
            for label_id in data['label_ids']:
                # Check each label we have cached and see if the ID matches.
                for label in self._labels:
                    if label['id'] == label_id:
                        # It does; add it to the list and move on.
                        task['labels'].append(label['name'])
                        break

        # If we have a label whitelist defined, check to see if we're
        # on the whitelist.
        if self._label_whitelist is not None:
            found_label = False
            for label in self._label_whitelist:
                # Check to see if the task has this label (in any case).
                found_label = label.lower() in (
                    task_label.lower() for task_label in task['labels'])
                if found_label:
                    break
            # Return invalid task if it's not on the whitelist.
            if not found_label:
                return None

        # Due dates (optional parameter).
        # The due date is the END date -- the task cannot be completed
        # past this time.
        # That means that the START date is the earliest time one can
        # complete the task.
        # Generally speaking, that means right now.
        task['start'] = datetime.utcnow()
        if 'due' in data:
            due_date = data['due']

            # Due dates are represented in RFC3339 format, in UTC.
            # Home Assistant exclusively uses UTC, so it'll
            # handle the conversion.
            if 'datetime' in due_date:
                task['end'] = datetime.strptime(
                    due_date['datetime'], '%Y-%m-%dT%H:%M:%SZ')
            else:
                task['end'] = datetime.strptime(due_date['date'], '%Y-%m-%d')

            if self._latest_due_date is not None and (
                    task['end'] > self._latest_due_date):
                # This task is out of range of our due date;
                # it shouldn't be counted.
                return None

            task['due_today'] = task['end'].date() == datetime.today().date()

            # Special case: Task is overdue.
            if task['end'] <= task['start']:
                task['overdue'] = True
                # Set end time to the current time plus 1 hour.
                # We're pretty much guaranteed to update within that 1 hour,
                # so it should be fine.
                task['end'] = task['start'] + timedelta(hours=1)
            else:
                task['overdue'] = False
        else:
            # If we ask for everything due before a certain date, don't count
            # things which have no due dates.
            if self._latest_due_date is not None:
                return None
            task['end'] = None
            task['all_day'] = True
            task['due_today'] = False
            task['overdue'] = False

        # Comments (optional parameter):
        task['comments'] = []
        if 'comment_count' in data and data['comment_count'] > 0:
            task_comments = requests.get(
                "https://beta.todoist.com/API/v8/comments",
                params={"token": self._token, "task_id": data['id']}
            ).json()
            for comment in task_comments:
                if 'attachment' in comment and (
                        'file_url' in comment['attachment']):
                    # Use the URL, if present
                    task['comments'].append(comment['attachment']['file_url'])
                else:
                    task['comments'].append(comment['content'])

        # Not tracked: id, project_id order, indent, recurring.
        return task

    @staticmethod
    def select_best_task(project_tasks):
        """
        Search through a list of events for the "best" event to select.

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
        if len(project_tasks) > 0:
            # Start at the end of the list, so if tasks don't have a due date
            # the newest ones are the most important.

            event = project_tasks[len(project_tasks) - 1]

            for proposed_event in project_tasks:
                if event == proposed_event:
                    continue
                if proposed_event['completed']:
                    # Event is complete!
                    continue
                if proposed_event['end'] is None:
                    # No end time:
                    if event['end'] is None and (
                            proposed_event['priority'] < event['priority']):
                        # They also have no end time,
                        # but we have a higher priority.
                        event = proposed_event
                        continue
                    else:
                        continue
                elif event['end'] is None:
                    # We have an end time, they do not.
                    event = proposed_event
                    continue
                if proposed_event['end'].date() > event['end'].date():
                    # Event is too late.
                    continue
                elif proposed_event['end'].date() < event['end'].date():
                    # Event is earlier than current, select it.
                    event = proposed_event
                    continue
                else:
                    if proposed_event['priority'] > event['priority']:
                        # Proposed event has a higher priority.
                        event = proposed_event
                        continue
                    elif proposed_event['priority'] == event['priority'] and (
                            proposed_event['end'] < event['end']):
                        event = proposed_event
                        continue
            return event
        else:
            # No tasks in array.
            return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        self.all_project_tasks = []

        if self._id is None:
            # Custom-defined task.
            if self._project_id_whitelist is None or (
                    len(self._project_id_whitelist) == 0):
                # No whitelist; grab all the projects.
                project_task_json_data = requests.get(
                    "https://beta.todoist.com/API/v8/tasks",
                    params={"token": self._token}
                ).json()
            else:
                # Grab each project from the whitelist.
                project_task_json_data = []
                for project_id in self._project_id_whitelist:
                    project_task_json_data.extend(requests.get(
                        "https://beta.todoist.com/API/v8/tasks",
                        params={
                            "token": self._token,
                            "project_id": project_id
                        }
                    ).json())
        else:
            # Todoist-defined task; grab tasks just for this project.
            project_task_json_data = requests.get(
                "https://beta.todoist.com/API/v8/tasks",
                params={"token": self._token, "project_id": self._id}
            ).json()

        # If we have no data, we can just return right away.
        if len(project_task_json_data) == 0:
            self.event = None
            return True

        # Keep an updated list of all tasks in this project.
        project_tasks = []

        for task in project_task_json_data:
            todoist_task = self.create_todoist_task(task)
            if todoist_task is not None:
                # A None task means it is invalid for this project
                project_tasks.append(todoist_task)

        if len(project_tasks) == 0:
            # We had no valid tasks
            return True

        # Organize the best tasks (so users can see all the tasks
        # they have, organized)
        while len(project_tasks) > 0:
            best_task = self.select_best_task(project_tasks)
            _LOGGER.info("Found Todoist Task: " + str(best_task))
            project_tasks.remove(best_task)
            self.all_project_tasks.append(best_task)

        self.event = self.all_project_tasks[0]

        # Convert datetime to a string again
        if self.event is not None:
            if self.event['start'] is not None:
                self.event['start'] = {
                    'dateTime': self.event['start'].strftime(DATE_STR_FORMAT)
                }
            if self.event['end'] is not None:
                self.event['end'] = {
                    'dateTime': self.event['end'].strftime(DATE_STR_FORMAT)
                }
            else:
                # HASS gets cranky if a calendar event never ends
                # Let's set our "due date" to tomorrow
                self.event['end'] = {
                    'dateTime': (
                        datetime.utcnow() +
                        timedelta(days=1)
                    ).strftime(DATE_STR_FORMAT)
                }
        _LOGGER.info("Updated " + self._name + ".")
        return True
