"""Event parser and human readable log generator."""
from __future__ import annotations

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.counter import DOMAIN as COUNTER_DOMAIN
from homeassistant.components.proximity import DOMAIN as PROXIMITY_DOMAIN
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import EVENT_CALL_SERVICE, EVENT_LOGBOOK_ENTRY

# Domains that are always continuous
ALWAYS_CONTINUOUS_DOMAINS = {COUNTER_DOMAIN, PROXIMITY_DOMAIN}

# Domains that are continuous if there is a UOM set on the entity
CONDITIONALLY_CONTINUOUS_DOMAINS = {SENSOR_DOMAIN}

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

# Automation events that can affect an entity_id or device_id
AUTOMATION_EVENTS = {EVENT_AUTOMATION_TRIGGERED, EVENT_SCRIPT_STARTED}

# Events that are built-in to the logbook or core
BUILT_IN_EVENTS = {EVENT_LOGBOOK_ENTRY, EVENT_CALL_SERVICE}

LOGBOOK_FILTERS = "logbook_filters"
LOGBOOK_ENTITIES_FILTER = "entities_filter"
