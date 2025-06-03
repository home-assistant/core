"""Constants for the Todoist component."""

from typing import Final

CONF_EXTRA_PROJECTS: Final = "custom_projects"
CONF_PROJECT_DUE_DATE: Final = "due_date_days"
CONF_PROJECT_LABEL_WHITELIST: Final = "labels"
CONF_PROJECT_WHITELIST: Final = "include_projects"

# Calendar Platform: Does this calendar event last all day?
ALL_DAY: Final = "all_day"
# Attribute: All tasks in this project
ALL_TASKS: Final = "all_tasks"
# Todoist API: "Completed" flag -- 1 if complete, else 0
CHECKED: Final = "checked"
# Attribute: Is this task complete?
COMPLETED: Final = "completed"
# Todoist API: What is this task about?
# Service Call: What is this task about?
CONTENT: Final = "content"
# Calendar Platform: Get a calendar event's description
DESCRIPTION: Final = "description"
# Calendar Platform: Used in the '_get_date()' method
DATETIME: Final = "dateTime"
DUE: Final = "due"
# Service Call: When is this task due (in natural language)?
DUE_DATE_STRING: Final = "due_date_string"
# Service Call: The language of DUE_DATE_STRING
DUE_DATE_LANG: Final = "due_date_lang"
# Service Call: When should user be reminded of this task (in natural language)?
REMINDER_DATE_STRING: Final = "reminder_date_string"
# Service Call: The language of REMINDER_DATE_STRING
REMINDER_DATE_LANG: Final = "reminder_date_lang"
# Service Call: The available options of DUE_DATE_LANG
DUE_DATE_VALID_LANGS: Final = [
    "en",
    "da",
    "pl",
    "zh",
    "ko",
    "de",
    "pt",
    "ja",
    "it",
    "fr",
    "sv",
    "ru",
    "es",
    "nl",
]
# Attribute: When is this task due?
# Service Call: When is this task due?
DUE_DATE: Final = "due_date"
# Service Call: When should user be reminded of this task?
REMINDER_DATE: Final = "reminder_date"
# Attribute: Is this task due today?
DUE_TODAY: Final = "due_today"
# Calendar Platform: When a calendar event ends
END: Final = "end"
# Todoist API: Look up a Project/Label/Task ID
ID: Final = "id"
# Todoist API: Fetch all labels
# Service Call: What are the labels attached to this task?
LABELS: Final = "labels"
# Todoist API: "Name" value
NAME: Final = "name"
# Todoist API: "Full Name" value
FULL_NAME: Final = "full_name"
# Attribute: Is this task overdue?
OVERDUE: Final = "overdue"
# Attribute: What is this task's priority?
# Todoist API: Get a task's priority
# Service Call: What is this task's priority?
PRIORITY: Final = "priority"
# Todoist API: Look up the Project ID a Task belongs to
PROJECT_ID: Final = "project_id"
# Service Call: What Project do you want a Task added to?
PROJECT_NAME: Final = "project"
# Todoist API: Fetch all Projects
PROJECTS: Final = "projects"
# Section Name: What Section of the Project do you want to add the Task to?
SECTION_NAME: Final = "section"
# Calendar Platform: When does a calendar event start?
START: Final = "start"
# Calendar Platform: What is the next calendar event about?
SUMMARY: Final = "summary"
# Todoist API: Fetch all Tasks
TASKS: Final = "items"
# Todoist API: "responsible" for a Task
ASSIGNEE: Final = "assignee"
# Todoist API: Collaborators in shared projects
COLLABORATORS: Final = "collaborators"

DOMAIN: Final = "todoist"

SERVICE_NEW_TASK: Final = "new_task"
