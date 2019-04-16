"""Permission constants for the websocket API.

Separate file to avoid circular imports.
"""
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED)
from homeassistant.components.persistent_notification import (
    EVENT_PERSISTENT_NOTIFICATIONS_UPDATED)

# These are events that do not contain any sensitive data
# Except for state_changed, which is handled accordingly.
SUBSCRIBE_WHITELIST = {
    EVENT_COMPONENT_LOADED,
    EVENT_PERSISTENT_NOTIFICATIONS_UPDATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
}
