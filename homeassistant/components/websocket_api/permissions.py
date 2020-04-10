"""Permission constants for the websocket API.

Separate file to avoid circular imports.
"""
from homeassistant.components.frontend import EVENT_PANELS_UPDATED
from homeassistant.components.lovelace.const import EVENT_LOVELACE_UPDATED
from homeassistant.components.persistent_notification import (
    EVENT_PERSISTENT_NOTIFICATIONS_UPDATED,
)
from homeassistant.components.shopping_list import EVENT as EVENT_SHOPPING_LIST_UPDATED
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
)
from homeassistant.helpers.area_registry import EVENT_AREA_REGISTRY_UPDATED
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

# These are events that do not contain any sensitive data
# Except for state_changed, which is handled accordingly.
SUBSCRIBE_WHITELIST = {
    EVENT_AREA_REGISTRY_UPDATED,
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_DEVICE_REGISTRY_UPDATED,
    EVENT_ENTITY_REGISTRY_UPDATED,
    EVENT_LOVELACE_UPDATED,
    EVENT_PANELS_UPDATED,
    EVENT_PERSISTENT_NOTIFICATIONS_UPDATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_SHOPPING_LIST_UPDATED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
}
