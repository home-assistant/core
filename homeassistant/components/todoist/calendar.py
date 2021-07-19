"""Support for Todoist task management (https://todoist.com)."""
from datetime import datetime, timedelta
import logging

from todoist.api import TodoistAPI
import voluptuous as vol

from homeassistant.components.calendar import PLATFORM_SCHEMA, CalendarEventDevice
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt

from .const import (
    ALL_DAY,
    ALL_TASKS,
    CHECKED,
    COMPLETED,
    CONF_EXTRA_PROJECTS,
    CONF_PROJECT_DUE_DATE,
    CONF_PROJECT_LABEL_WHITELIST,
    CONF_PROJECT_WHITELIST,
    CONTENT,
    DATETIME,
    DESCRIPTION,
    DOMAIN,
    DUE,
    DUE_DATE,
    DUE_DATE_LANG,
    DUE_DATE_STRING,
    DUE_DATE_VALID_LANGS,
    DUE_TODAY,
    END,
    ID,
    LABELS,
    NAME,
    OVERDUE,
    PRIORITY,
    PROJECT_ID,
    PROJECT_NAME,
    PROJECTS,
    REMINDER_DATE,
    REMINDER_DATE_LANG,
    REMINDER_DATE_STRING,
    SERVICE_NEW_TASK,
    START,
    SUMMARY,
    TASKS,
)

_LOGGER = logging.getLogger(__name__)

NEW_TASK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONTENT): cv.string,
        vol.Optional(PROJECT_NAME, default="inbox"): vol.All(cv.string, vol.Lower),
        vol.Optional(LABELS): cv.ensure_list_csv,
        vol.Optional(PRIORITY): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Exclusive(DUE_DATE_STRING, "due_date"): cv.string,
        vol.Optional(DUE_DATE_LANG): vol.All(cv.string, vol.In(DUE_DATE_VALID_LANGS)),
        vol.Exclusive(DUE_DATE, "due_date"): cv.string,
        vol.Exclusive(REMINDER_DATE_STRING, "reminder_date"): cv.string,
        vol.Optional(REMINDER_DATE_LANG): vol.All(
            cv.string, vol.In(DUE_DATE_VALID_LANGS)
        ),
        vol.Exclusive(REMINDER_DATE, "reminder_date"): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
                            ): vol.All(cv.ensure_list, [vol.All(cv.string, vol.Lower)]),
                        }
                    )
                ]
            ),
        ),
    }
)

SCAN_INTERVAL = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Todoist platform."""
    token = config.get(CONF_TOKEN)

    # Look up IDs based on (lowercase) names.
    project_id_lookup = {}
    label_id_lookup = {}

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
        project_data = {CONF_NAME: project[NAME], CONF_ID: project[ID]}
        project_devices.append(TodoistProjectDevice(hass, project_data, labels, api))
        # Cache the names so we can easily look up name->ID.
        project_id_lookup[project[NAME].lower()] = project[ID]

    # Cache all label names
    for label in labels:
        label_id_lookup[label[NAME].lower()] = label[ID]

    # Check config for more projects.
    extra_projects = config[CONF_EXTRA_PROJECTS]
    for project in extra_projects:
        # Special filter: By date
        project_due_date = project.get(CONF_PROJECT_DUE_DATE)

        # Special filter: By label
        project_label_filter = project[CONF_PROJECT_LABEL_WHITELIST]

        # Special filter: By name
        # Names must be converted into IDs.
        project_name_filter = project[CONF_PROJECT_WHITELIST]
        project_id_filter = [
            project_id_lookup[project_name.lower()]
            for project_name in project_name_filter
        ]

        # Create the custom project and add it to the devices array.
        project_devices.append(
            TodoistProjectDevice(
                hass,
                project,
                labels,
                api,
                project_due_date,
                project_label_filter,
                project_id_filter,
            )
        )

    add_entities(project_devices)

    def handle_new_task(call):
        """Call when a user creates a new Todoist Task from Home Assistant."""
        project_name = call.data[PROJECT_NAME]
        project_id = project_id_lookup[project_name]

        # Create the task
        item = api.items.add(call.data[CONTENT], project_id=project_id)

        if LABELS in call.data:
            task_labels = call.data[LABELS]
            label_ids = [label_id_lookup[label.lower()] for label in task_labels]
            item.update(labels=label_ids)

        if PRIORITY in call.data:
            item.update(priority=call.data[PRIORITY])

        _due: dict = {}
        if DUE_DATE_STRING in call.data:
            _due["string"] = call.data[DUE_DATE_STRING]

        if DUE_DATE_LANG in call.data:
            _due["lang"] = call.data[DUE_DATE_LANG]

        if DUE_DATE in call.data:
            due_date = dt.parse_datetime(call.data[DUE_DATE])
            if due_date is None:
                due = dt.parse_date(call.data[DUE_DATE])
                due_date = datetime(due.year, due.month, due.day)
            # Format it in the manner Todoist expects
            due_date = dt.as_utc(due_date)
            date_format = "%Y-%m-%dT%H:%M%S"
            due_date = datetime.strftime(due_date, date_format)
            _due["date"] = due_date

        if _due:
            item.update(due=_due)

        _reminder_due: dict = {}
        if REMINDER_DATE_STRING in call.data:
            _reminder_due["string"] = call.data[REMINDER_DATE_STRING]

        if REMINDER_DATE_LANG in call.data:
            _reminder_due["lang"] = call.data[REMINDER_DATE_LANG]

        if REMINDER_DATE in call.data:
            due_date = dt.parse_datetime(call.data[REMINDER_DATE])
            if due_date is None:
                due = dt.parse_date(call.data[REMINDER_DATE])
                due_date = datetime(due.year, due.month, due.day)
            # Format it in the manner Todoist expects
            due_date = dt.as_utc(due_date)
            date_format = "%Y-%m-%dT%H:%M:%S"
            due_date = datetime.strftime(due_date, date_format)
            _reminder_due["date"] = due_date

        if _reminder_due:
            api.reminders.add(item["id"], due=_reminder_due)

        # Commit changes
        api.commit()
        _LOGGER.debug("Created Todoist task: %s", call.data[CONTENT])

    hass.services.register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )


def _parse_due_date(data: dict, gmt_string) -> datetime:
    """Parse the due date dict into a datetime object."""
    # Add time information to date only strings.
    if len(data["date"]) == 10:
        return datetime.fromisoformat(data["date"]).replace(tzinfo=dt.UTC)
    if dt.parse_datetime(data["date"]).tzinfo is None:
        data["date"] += gmt_string
    return dt.as_utc(dt.parse_datetime(data["date"]))


class TodoistProjectDevice(CalendarEventDevice):
    """A device for getting the next Task from a Todoist Project."""

    def __init__(
        self,
        hass,
        data,
        labels,
        token,
        due_date_days=None,
        whitelisted_labels=None,
        whitelisted_projects=None,
    ):
        """Create the Todoist Calendar Event Device."""
        self.data = TodoistProjectData(
            data,
            labels,
            token,
            due_date_days,
            whitelisted_labels,
            whitelisted_projects,
        )
        self._cal_data = {}
        self._name = data[CONF_NAME]

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.data.event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update all Todoist Calendars."""
        self.data.update()
        # Set Todoist-specific data that can't easily be grabbed
        self._cal_data[ALL_TASKS] = [
            task[SUMMARY] for task in self.data.all_project_tasks
        ]

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return None

        return {
            DUE_TODAY: self.data.event[DUE_TODAY],
            OVERDUE: self.data.event[OVERDUE],
            ALL_TASKS: self._cal_data[ALL_TASKS],
            PRIORITY: self.data.event[PRIORITY],
            LABELS: self.data.event[LABELS],
        }


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
    as any updates to current projects/tasks. This occurs every SCAN_INTERVAL minutes.
    """

    def __init__(
        self,
        project_data,
        labels,
        api,
        due_date_days=None,
        whitelisted_labels=None,
        whitelisted_projects=None,
    ):
        """Initialize a Todoist Project."""
        self.event = None

        self._api = api
        self._name = project_data[CONF_NAME]
        # If no ID is defined, fetch all tasks.
        self._id = project_data.get(CONF_ID)

        # All labels the user has defined, for easy lookup.
        self._labels = labels
        # Not tracked: order, indent, comment_count.

        self.all_project_tasks = []

        # The days a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        if due_date_days is not None:
            self._due_date_days = timedelta(days=due_date_days)
        else:
            self._due_date_days = None

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
        task[DESCRIPTION] = f"https://todoist.com/showTask?id={data[ID]}"

        # All task Labels (optional parameter).
        task[LABELS] = [
            label[NAME].lower() for label in self._labels if label[ID] in data[LABELS]
        ]

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
        task[START] = dt.utcnow()
        if data[DUE] is not None:
            task[END] = _parse_due_date(
                data[DUE], self._api.state["user"]["tz_info"]["gmt_string"]
            )

            if self._due_date_days is not None and (
                task[END] > dt.utcnow() + self._due_date_days
            ):
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
                proposed_event[END] < event[END]
            ):
                event = proposed_event
                continue

        return event

    async def async_get_events(self, hass, start_date, end_date):
        """Get all tasks in a specific time frame."""
        if self._id is None:
            project_task_data = [
                task
                for task in self._api.state[TASKS]
                if not self._project_id_whitelist
                or task[PROJECT_ID] in self._project_id_whitelist
            ]
        else:
            project_data = await hass.async_add_executor_job(
                self._api.projects.get_data, self._id
            )
            project_task_data = project_data[TASKS]

        events = []
        for task in project_task_data:
            if task["due"] is None:
                continue
            due_date = _parse_due_date(
                task["due"], self._api.state["user"]["tz_info"]["gmt_string"]
            )
            midnight = dt.as_utc(
                dt.parse_datetime(
                    due_date.strftime("%Y-%m-%d")
                    + "T00:00:00"
                    + self._api.state["user"]["tz_info"]["gmt_string"]
                )
            )

            if start_date < due_date < end_date:
                if due_date == midnight:
                    # If the due date has no time data, return just the date so that it
                    # will render correctly as an all day event on a calendar.
                    due_date_value = due_date.strftime("%Y-%m-%d")
                else:
                    due_date_value = due_date.isoformat()
                event = {
                    "uid": task["id"],
                    "title": task["content"],
                    "start": due_date_value,
                    "end": due_date_value,
                    "allDay": True,
                    "summary": task["content"],
                }
                events.append(event)
        return events

    def update(self):
        """Get the latest data."""
        if self._id is None:
            self._api.reset_state()
            self._api.sync()
            project_task_data = [
                task
                for task in self._api.state[TASKS]
                if not self._project_id_whitelist
                or task[PROJECT_ID] in self._project_id_whitelist
            ]
        else:
            project_task_data = self._api.projects.get_data(self._id)[TASKS]

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

        self.event = self.all_project_tasks[0]

        # Convert datetime to a string again
        if self.event is not None:
            if self.event[START] is not None:
                self.event[START] = {
                    DATETIME: self.event[START].strftime(DATE_STR_FORMAT)
                }
            if self.event[END] is not None:
                self.event[END] = {DATETIME: self.event[END].strftime(DATE_STR_FORMAT)}
            else:
                # Home Assistant gets cranky if a calendar event never ends
                # Let's set our "due date" to tomorrow
                self.event[END] = {
                    DATETIME: (datetime.utcnow() + timedelta(days=1)).strftime(
                        DATE_STR_FORMAT
                    )
                }
        _LOGGER.debug("Updated %s", self._name)
