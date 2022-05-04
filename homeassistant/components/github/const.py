"""Constants for the GitHub integration."""
from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "github"

CLIENT_ID = "1440cafcc86e3ea5d6a2"

DEFAULT_REPOSITORIES = ["home-assistant/core", "esphome/esphome"]
FALLBACK_UPDATE_INTERVAL = timedelta(hours=1, minutes=30)

CONF_ACCESS_TOKEN = "access_token"
CONF_REPOSITORIES = "repositories"


REFRESH_EVENT_TYPES = (
    "CreateEvent",
    "ForkEvent",
    "IssuesEvent",
    "PullRequestEvent",
    "PushEvent",
    "ReleaseEvent",
    "WatchEvent",
)
