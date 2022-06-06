"""Event parser and human readable log generator."""
from __future__ import annotations

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.const import EVENT_CALL_SERVICE, EVENT_LOGBOOK_ENTRY

ATTR_MESSAGE = "message"

DOMAIN = "logbook"

CONTEXT_USER_ID = "context_user_id"
CONTEXT_ENTITY_ID = "context_entity_id"
CONTEXT_ENTITY_ID_NAME = "context_entity_id_name"
CONTEXT_EVENT_TYPE = "context_event_type"
CONTEXT_DOMAIN = "context_domain"
CONTEXT_STATE = "context_state"
CONTEXT_SOURCE = "context_source"
CONTEXT_SERVICE = "context_service"
CONTEXT_NAME = "context_name"
CONTEXT_MESSAGE = "context_message"

LOGBOOK_ENTRY_CONTEXT_ID = "context_id"
LOGBOOK_ENTRY_DOMAIN = "domain"
LOGBOOK_ENTRY_ENTITY_ID = "entity_id"
LOGBOOK_ENTRY_ICON = "icon"
LOGBOOK_ENTRY_SOURCE = "source"
LOGBOOK_ENTRY_MESSAGE = "message"
LOGBOOK_ENTRY_NAME = "name"
LOGBOOK_ENTRY_STATE = "state"
LOGBOOK_ENTRY_WHEN = "when"

ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED = {EVENT_LOGBOOK_ENTRY, EVENT_CALL_SERVICE}
ENTITY_EVENTS_WITHOUT_CONFIG_ENTRY = {
    EVENT_LOGBOOK_ENTRY,
    EVENT_AUTOMATION_TRIGGERED,
    EVENT_SCRIPT_STARTED,
}


LOGBOOK_FILTERS = "logbook_filters"
LOGBOOK_ENTITIES_FILTER = "entities_filter"
