"""Constants for the Todoist component."""
CONF_EXTRA_PROJECTS = "custom_projects"
CONF_PROJECT_DUE_DATE = "due_date_days"
CONF_PROJECT_LABEL_WHITELIST = "labels"
CONF_PROJECT_WHITELIST = "include_projects"

# Calendar Platform: Does this calendar event last all day?
ALL_DAY = "all_day"
# Attribute: All tasks in this project
ALL_TASKS = "all_tasks"
# Todoist API: "Completed" flag -- 1 if complete, else 0
CHECKED = "checked"
# Attribute: Is this task complete?
COMPLETED = "completed"
# Todoist API: What is this task about?
# Service Call: What is this task about?
CONTENT = "content"
# Calendar Platform: Get a calendar event's description
DESCRIPTION = "description"
# Calendar Platform: Used in the '_get_date()' method
DATETIME = "dateTime"
DUE = "due"
# Service Call: When is this task due (in natural language)?
DUE_DATE_STRING = "due_date_string"
# Service Call: The language of DUE_DATE_STRING
DUE_DATE_LANG = "due_date_lang"
# Service Call: The available options of DUE_DATE_LANG
DUE_DATE_VALID_LANGS = [
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
DUE_DATE = "due_date"
# Attribute: Is this task due today?
DUE_TODAY = "due_today"
# Calendar Platform: When a calendar event ends
END = "end"
# Todoist API: Look up a Project/Label/Task ID
ID = "id"
# Todoist API: Fetch all labels
# Service Call: What are the labels attached to this task?
LABELS = "labels"
# Todoist API: "Name" value
NAME = "name"
# Attribute: Is this task overdue?
OVERDUE = "overdue"
# Attribute: What is this task's priority?
# Todoist API: Get a task's priority
# Service Call: What is this task's priority?
PRIORITY = "priority"
# Todoist API: Look up the Project ID a Task belongs to
PROJECT_ID = "project_id"
# Service Call: What Project do you want a Task added to?
PROJECT_NAME = "project"
# Todoist API: Fetch all Projects
PROJECTS = "projects"
# Calendar Platform: When does a calendar event start?
START = "start"
# Calendar Platform: What is the next calendar event about?
SUMMARY = "summary"
# Todoist API: Fetch all Tasks
TASKS = "items"

DOMAIN = "todoist"

SERVICE_NEW_TASK = "new_task"
