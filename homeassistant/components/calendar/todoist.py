import requests
import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.components.google import (
    CONF_DEVICE_ID, CONF_NAME)
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.components.calendar import CalendarEventDevice
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
# Your Todoist API token, found at https://todoist.com/Users/viewPrefs?page=authorizations
CONF_API_TOKEN = 'token'
CONF_EXTRA_PROJECTS = 'extra_projects'
CONF_PROJECT_NAME = 'name'
CONF_PROJECT_DUE_DATE = 'due_date_days'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    token = config.get(CONF_API_TOKEN)

    # Grab all projects
    projects = requests.get('https://beta.todoist.com/API/v8/projects',
        params={'token': token}
    ).json()

    project_devices = []
    for project in projects:
        project_devices.append(TodoistProjectDevice(hass, project, token))

    # Check config for more projects
    extra_projects = config.get(CONF_EXTRA_PROJECTS)
    if extra_projects is not None:
        for project in extra_projects:
            project_devices.append(TodoistProjectDevice(hass, project, token, project.get(CONF_PROJECT_DUE_DATE)))

    add_devices(project_devices)

class TodoistProjectDevice(CalendarEventDevice):
    """
    A device for getting the next Task from a Todoist Project.
    """
    def __init__(self, hass, data, token, latest_task_due_date=None):
        """Create the Todoist Calendar Event Device."""

        self.data = TodoistProjectData(data, token, latest_task_due_date)

        # Set up the calendar side of things
        calendar_format = {}
        calendar_format[CONF_NAME] = data['name']
        calendar_format[CONF_DEVICE_ID] = data['name']

        super().__init__(hass, calendar_format)

    def update(self):
        super().update()

        if self.data.event is not None and 'all_day' in self.data.event:
            # This event doesn't have an end time, so we mark it as all day
            self._cal_data['all_day'] = True

        self._cal_data['all_tasks'] = []
        for task in self.data.all_project_tasks:
            self._cal_data['all_tasks'].append(task['summary'])

    def cleanup(self):
        super().cleanup()
        self._cal_data['all_tasks'] = []

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            return {}

        attributes = super().device_state_attributes
        # Add additional attributes
        attributes['due_today'] = self.data.event['due_today']
        attributes['all_tasks'] = self._cal_data['all_tasks']
        attributes['priority'] = self.data.event['priority']
        return attributes

class TodoistProjectData(object):
    """
    Class used by the Task Device service object to hold all Todoist Tasks.
    Takes a JSON representation of the project data (returned from the Todoist API),
    a Todoist API token, and an optional integer specifying the latest number of days
    from now a task can be due (7 means everything due in the next week, 0 means
    today, etc.).
    """
    def __init__(self, project_data, token, latest_task_due_date=None):
        self.event = None

        self._token = token
        self._name = project_data['name']
        # If no ID is defined, fetch all tasks
        if 'id' in project_data:
            self._id = project_data['id']
        else:
            self._id = None
        # Not tracked: order, indent, comment_count

        self.all_project_tasks = []
        # The latest date a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example)
        if latest_task_due_date is not None:
            self._latest_due_date = datetime.now() + timedelta(days=latest_task_due_date)
        else:
            self._latest_due_date = None

    def create_todoist_task(self, data):
        task = {}
        # Fields are required to be in all returned task objects
        task['summary'] = data['content']
        task['completed'] = data['completed']
        task['priority'] = data['priority']
        task['description'] = data['url']

        # Due dates (optional parameter)
        # The due date is the END date -- the task cannot be completed past this time
        # That means that the START date is the earliest time one can complete the task
        # Generally speaking, that means right now
        task['start'] = datetime.utcnow()
        if 'due' in data:
            due_date = data['due']

            # Due dates are represented in RFC3339 format, in UTC
            # Home Assistant exclusively uses UTC, so it'll handle the conversion
            if 'datetime' in due_date:
                task['end'] = datetime.strptime(due_date['datetime'], '%Y-%m-%dT%H:%M:%SZ')
            else:
                task['end'] = datetime.strptime(due_date['date'], '%Y-%m-%d')

            if self._latest_due_date is not None and task['end'] > self._latest_due_date:
                # This task is out of range of our due date; it shouldn't be counted
                return None

            task['due_today'] = task['end'].date() == datetime.today().date()
        else:
            # If we ask for everything due before a certain date, don't count things
            # which have no due dates
            if self._latest_due_date is not None:
                return None
            task['end'] = None
            task['all_day'] = True
            task['due_today'] = False
        # Not tracked: id, project_id order, indent, comment_count, label_ids, recurring
        return task

    def select_best_task(self, project_tasks):
        if len(project_tasks) > 0:
            # Start at the end of the list, so if tasks don't have a due date
            # the newest ones are the most important
            event = project_tasks[len(project_tasks) - 1]
            """
            Search through all our events for the "best" event to select
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

            for proposed_event in project_tasks:
                if event == proposed_event:
                    continue
                if proposed_event['completed']:
                    # Event is complete
                    continue
                if proposed_event['end'] is None:
                    # No end time
                    if event['end'] is None and proposed_event['priority'] < event['priority']:
                        # They also have no end time, but we have a higher priority
                        event = proposed_event
                        continue
                    else:
                        continue
                elif event['end'] is None:
                    # We have an end time, they do not
                    event = proposed_event
                    continue
                if proposed_event['end'].date() > event['end'].date():
                    # Event is too late
                    continue
                elif proposed_event['end'].date() < event['end'].date():
                    # Event is earlier than current, select it
                    event = proposed_event
                    continue
                else:
                    if proposed_event['priority'] > event['priority']:
                        # Proposed event has a higher priority
                        event = proposed_event
                        continue
                    elif proposed_event['priority'] == event['priority'] and proposed_event['end'] < event['end']:
                        event = proposed_event
                        continue
            return event
        else:
            # No tasks in array
            return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        self.all_project_tasks = []

        if self._id is None:
            # Grab all tasks
            project_task_json_data = requests.get("https://beta.todoist.com/API/v8/tasks",
                params={"token": self._token}
            ).json()
        else:
            # Grab tasks just for this project
            project_task_json_data = requests.get("https://beta.todoist.com/API/v8/tasks",
                params={"token": self._token, "project_id": self._id}
            ).json()

        # If we have no data, we can just return right away
        if len(project_task_json_data) == 0:
            self.event = None
            return True

        # Keep an updated list of all tasks in this project
        project_tasks = []

        for task in project_task_json_data:
            todoist_task = self.create_todoist_task(task)
            if todoist_task is not None:
                # A None task means it is invalid for this project
                project_tasks.append(todoist_task)

        if len(project_tasks) == 0:
            # We had no valid tasks
            return True

        # Organize the best tasks (so users can see all the tasks they have, organized)
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
                    'dateTime': (datetime.utcnow() + timedelta(days=1)).strftime(DATE_STR_FORMAT)
                }
        return True
