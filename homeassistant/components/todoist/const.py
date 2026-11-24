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
# Calendar Platform: Get a calendar event's description
DESCRIPTION: Final = "description"
# Calendar Platform: Used in the '_get_date()' method
DATETIME: Final = "dateTime"
DUE: Final = "due"
# Service Call: The available options of the due and reminder date languages
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
# Attribute: Is this task due today?
DUE_TODAY: Final = "due_today"
# Calendar Platform: When a calendar event ends
END: Final = "end"
# Todoist API: Look up a Project/Label/Task ID
ID: Final = "id"
# Todoist API: Fetch all labels
LABELS: Final = "labels"
# Todoist API: "Name" value
NAME: Final = "name"
# Todoist API: "Full Name" value
FULL_NAME: Final = "full_name"
# Attribute: Is this task overdue?
OVERDUE: Final = "overdue"
# Attribute: What is this task's priority?
# Todoist API: Get a task's priority
PRIORITY: Final = "priority"
# Todoist API: Look up the Project ID a Task belongs to
PROJECT_ID: Final = "project_id"
# Todoist API: Fetch all Projects
PROJECTS: Final = "projects"
# Calendar Platform: When does a calendar event start?
START: Final = "start"
# Calendar Platform: What is the next calendar event about?
SUMMARY: Final = "summary"
# Todoist API: Fetch all Tasks
TASKS: Final = "items"
# Todoist API: Collaborators in shared projects
COLLABORATORS: Final = "collaborators"

DOMAIN: Final = "todoist"

# Maximum number of items per page for Todoist API requests
MAX_PAGE_SIZE: Final = 200
