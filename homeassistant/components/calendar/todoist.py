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

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    token = config.get(CONF_API_TOKEN)
    projects = requests.get('https://beta.todoist.com/API/v8/projects',
        params={'token': token}
    ).json()

    project_devices = []
    for project in projects:
        project_devices.append(TodoistProjectDevice(hass, project, token))

    add_devices(project_devices)

class TodoistProjectDevice(CalendarEventDevice):
    """
    A device for getting the next Task from a Todoist Project.
    """
    def __init__(self, hass, data, token):
        """Create the Todoist Calendar Event Device."""

        self.data = TodoistProjectData(data, token)

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
        attributes['all_tasks'] = self._cal_data['all_tasks']
        return attributes

class TodoistProjectData(object):
    """Class used by the Task Device service object to get the next task."""
    def __init__(self, project_data, token):
        self._token = token
        self._name = project_data['name']
        self._id = project_data['id']
        # Not tracked: order, indent, comment_count

        self.all_project_tasks = []

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
        else:
            task['end'] = None
            task['all_day'] = True
        # Not tracked: id, project_id order, indent, comment_count, label_ids, recurring
        return task

    def select_best_task(self, project_tasks):
        if len(project_tasks) > 0:
            event = project_tasks[0]
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
                    if proposed_event['priority'] < event['priority']:
                        # Proposed event has a higher priority (lower number)
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
            project_tasks.append(self.create_todoist_task(task))

        # Organize the best tasks (so users can see all the tasks they have, organized)
        while len(project_tasks) > 0:
            best_task = self.select_best_task(project_tasks)
            _LOGGER.warning(best_task)
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
