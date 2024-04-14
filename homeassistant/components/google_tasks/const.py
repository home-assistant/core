"""Constants for the Google Tasks integration."""

from enum import StrEnum

DOMAIN = "google_tasks"

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"
OAUTH2_SCOPES = ["https://www.googleapis.com/auth/tasks"]


class TaskStatus(StrEnum):
    """Status of a Google Task."""

    NEEDS_ACTION = "needsAction"
    COMPLETED = "completed"
