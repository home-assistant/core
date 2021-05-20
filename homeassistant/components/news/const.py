"""Constants for the news integration."""
from datetime import timedelta
from enum import Enum

import voluptuous as vol

DOMAIN = "news"
STORAGE_KEY = "core.news"
STORAGE_VERSION = 1
SOURCE_UPDATE_INTERVAL = timedelta(hours=1)

SOURCES_SCHEMA = vol.Schema({vol.Required("alerts"): bool})
EVENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("title", default=None): vol.Any(str, None),
        vol.Optional("description", default=None): vol.Any(str, None),
        vol.Optional("url", default=None): vol.Any(str, None),
    }
)

DISPATCHER_NEWS_EVENT = "news_event"

ATTR_ACTIVE = "active"
ATTR_ALERT_URL = "alert_url"
ATTR_CREATED = "created"
ATTR_DESCRIPTION = "description"
ATTR_DISMISSED = "dismissed"
ATTR_EVENTS = "events"
ATTR_HOMEASSISTANT = "homeassistant"
ATTR_INTEGRATIONS = "integrations"
ATTR_MAX = "max"
ATTR_MIN = "min"
ATTR_PACKAGE = "package"
ATTR_SOURCE = "source"
ATTR_SOURCES = "sources"
ATTR_TITLE = "title"
ATTR_URL = "url"


class NewsSource(str, Enum):
    """News source."""

    ALERTS = "alerts"
