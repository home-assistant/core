"""Event parser and human readable log generator."""
from datetime import timedelta
from itertools import groupby
import json
import logging

import sqlalchemy
from sqlalchemy.orm import aliased
import voluptuous as vol

from homeassistant.components import sun
from homeassistant.components.history import sqlalchemy_filter_from_include_exclude_conf
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder.models import (
    Events,
    States,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    HTTP_BAD_REQUEST,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
    generate_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_MESSAGE = "message"

CONF_DOMAINS = "domains"
CONF_ENTITIES = "entities"
CONTINUOUS_DOMAINS = ["proximity", "sensor"]

DOMAIN = "logbook"

GROUP_BY_MINUTES = 15

EMPTY_JSON_OBJECT = "{}"
UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA}, extra=vol.ALLOW_EXTRA
)

HOMEASSISTANT_EVENTS = [
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
]

ALL_EVENT_TYPES = [EVENT_STATE_CHANGED, EVENT_LOGBOOK_ENTRY, *HOMEASSISTANT_EVENTS]

LOG_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_DOMAIN): cv.slug,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@bind_hass
def log_entry(hass, name, message, domain=None, entity_id=None):
    """Add an entry to the logbook."""
    hass.add_job(async_log_entry, hass, name, message, domain, entity_id)


@bind_hass
def async_log_entry(hass, name, message, domain=None, entity_id=None):
    """Add an entry to the logbook."""
    data = {ATTR_NAME: name, ATTR_MESSAGE: message}

    if domain is not None:
        data[ATTR_DOMAIN] = domain
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id
    hass.bus.async_fire(EVENT_LOGBOOK_ENTRY, data)


async def async_setup(hass, config):
    """Logbook setup."""
    hass.data[DOMAIN] = {}

    @callback
    def log_message(service):
        """Handle sending notification message service calls."""
        message = service.data[ATTR_MESSAGE]
        name = service.data[ATTR_NAME]
        domain = service.data.get(ATTR_DOMAIN)
        entity_id = service.data.get(ATTR_ENTITY_ID)

        if entity_id is None and domain is None:
            # If there is no entity_id or
            # domain, the event will get filtered
            # away so we use the "logbook" domain
            domain = DOMAIN

        message.hass = hass
        message = message.async_render()
        async_log_entry(hass, name, message, domain, entity_id)

    hass.components.frontend.async_register_built_in_panel(
        "logbook", "logbook", "hass:format-list-bulleted-type"
    )

    conf = config.get(DOMAIN, {})

    if conf:
        filters = sqlalchemy_filter_from_include_exclude_conf(conf)
        entities_filter = convert_include_exclude_filter(conf)
    else:
        filters = None
        entities_filter = None

    hass.http.register_view(LogbookView(conf, filters, entities_filter))

    hass.services.async_register(DOMAIN, "log", log_message, schema=LOG_MESSAGE_SCHEMA)

    await async_process_integration_platforms(hass, DOMAIN, _process_logbook_platform)

    return True


async def _process_logbook_platform(hass, domain, platform):
    """Process a logbook platform."""

    @callback
    def _async_describe_event(domain, event_name, describe_callback):
        """Teach logbook how to describe a new event."""
        hass.data[DOMAIN][event_name] = (domain, describe_callback)

    platform.async_describe_events(hass, _async_describe_event)


class LogbookView(HomeAssistantView):
    """Handle logbook view requests."""

    url = "/api/logbook"
    name = "api:logbook"
    extra_urls = ["/api/logbook/{datetime}"]

    def __init__(self, config, filters, entities_filter):
        """Initialize the logbook view."""
        self.config = config
        self.filters = filters
        self.entities_filter = entities_filter

    async def get(self, request, datetime=None):
        """Retrieve logbook entries."""
        if datetime:
            datetime = dt_util.parse_datetime(datetime)

            if datetime is None:
                return self.json_message("Invalid datetime", HTTP_BAD_REQUEST)
        else:
            datetime = dt_util.start_of_local_day()

        period = request.query.get("period")
        if period is None:
            period = 1
        else:
            period = int(period)

        entity_id = request.query.get("entity")

        end_time = request.query.get("end_time")
        if end_time is None:
            start_day = dt_util.as_utc(datetime) - timedelta(days=period - 1)
            end_day = start_day + timedelta(days=period)
        else:
            start_day = datetime
            end_day = dt_util.parse_datetime(end_time)
            if end_day is None:
                return self.json_message("Invalid end_time", HTTP_BAD_REQUEST)

        hass = request.app["hass"]

        def json_events():
            """Fetch events and generate JSON."""
            return self.json(
                _get_events(
                    hass,
                    self.config,
                    start_day,
                    end_day,
                    entity_id,
                    self.filters,
                    self.entities_filter,
                )
            )

        return await hass.async_add_job(json_events)


def humanify(hass, events, entity_attr_cache, prev_states=None):
    """Generate a converted list of events into Entry objects.

    Will try to group events if possible:
    - if 2+ sensor updates in GROUP_BY_MINUTES, show last
    - if Home Assistant stop and start happen in same minute call it restarted
    """
    if prev_states is None:
        prev_states = {}

    # Group events in batches of GROUP_BY_MINUTES
    for _, g_events in groupby(
        events, lambda event: event.time_fired_minute // GROUP_BY_MINUTES
    ):

        events_batch = list(g_events)

        # Keep track of last sensor states
        last_sensor_event = {}

        # Group HA start/stop events
        # Maps minute of event to 1: stop, 2: stop + start
        start_stop_events = {}

        # Process events
        for event in events_batch:
            if event.event_type == EVENT_STATE_CHANGED:
                if event.domain in CONTINUOUS_DOMAINS:
                    last_sensor_event[event.entity_id] = event

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if event.time_fired_minute in start_stop_events:
                    continue

                start_stop_events[event.time_fired_minute] = 1

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if event.time_fired_minute not in start_stop_events:
                    continue

                start_stop_events[event.time_fired_minute] = 2

        # Yield entries
        external_events = hass.data.get(DOMAIN, {})
        for event in events_batch:
            if event.event_type in external_events:
                domain, describe_event = external_events[event.event_type]
                data = describe_event(event)
                data["when"] = event.time_fired_isoformat
                data["domain"] = domain
                data["context_user_id"] = event.context_user_id
                yield data

            if event.event_type == EVENT_STATE_CHANGED:
                entity_id = event.entity_id

                # Skip events that have not changed state
                if entity_id in prev_states and prev_states[entity_id] == event.state:
                    continue

                prev_states[entity_id] = event.state
                domain = event.domain

                if (
                    domain in CONTINUOUS_DOMAINS
                    and event != last_sensor_event[entity_id]
                ):
                    # Skip all but the last sensor state
                    continue

                name = entity_attr_cache.get(
                    entity_id, ATTR_FRIENDLY_NAME, event
                ) or split_entity_id(entity_id)[1].replace("_", " ")

                yield {
                    "when": event.time_fired_isoformat,
                    "name": name,
                    "message": _entry_message_from_event(
                        hass, entity_id, domain, event, entity_attr_cache
                    ),
                    "domain": domain,
                    "entity_id": entity_id,
                    "context_user_id": event.context_user_id,
                }

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(event.time_fired_minute) == 2:
                    continue

                yield {
                    "when": event.time_fired_isoformat,
                    "name": "Home Assistant",
                    "message": "started",
                    "domain": HA_DOMAIN,
                    "context_user_id": event.context_user_id,
                }

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if start_stop_events.get(event.time_fired_minute) == 2:
                    action = "restarted"
                else:
                    action = "stopped"

                yield {
                    "when": event.time_fired_isoformat,
                    "name": "Home Assistant",
                    "message": action,
                    "domain": HA_DOMAIN,
                    "context_user_id": event.context_user_id,
                }

            elif event.event_type == EVENT_LOGBOOK_ENTRY:
                event_data = event.data
                domain = event_data.get(ATTR_DOMAIN)
                entity_id = event_data.get(ATTR_ENTITY_ID)
                if domain is None and entity_id is not None:
                    try:
                        domain = split_entity_id(str(entity_id))[0]
                    except IndexError:
                        pass

                yield {
                    "when": event.time_fired_isoformat,
                    "name": event_data.get(ATTR_NAME),
                    "message": event_data.get(ATTR_MESSAGE),
                    "domain": domain,
                    "entity_id": entity_id,
                }


def _get_events(
    hass, config, start_day, end_day, entity_id=None, filters=None, entities_filter=None
):
    """Get events for a period of time."""
    entity_attr_cache = EntityAttributeCache(hass)

    def yield_events(query):
        """Yield Events that are not filtered away."""
        for row in query.yield_per(1000):
            event = LazyEventPartialState(row)
            if _keep_event(hass, event, entities_filter, entity_attr_cache):
                yield event

    with session_scope(hass=hass) as session:
        if entity_id is not None:
            entity_ids = [entity_id.lower()]
            entities_filter = generate_filter([], entity_ids, [], [])
            apply_sql_entities_filter = False
        else:
            entity_ids = None
            apply_sql_entities_filter = True

        old_state = aliased(States, name="old_state")

        query = (
            session.query(
                Events.event_type,
                Events.event_data,
                Events.time_fired,
                Events.context_user_id,
                States.state_id,
                States.state,
                States.entity_id,
                States.domain,
                States.attributes,
                old_state.state_id.label("old_state_id"),
            )
            .order_by(Events.time_fired)
            .outerjoin(States, (Events.event_id == States.event_id))
            .outerjoin(old_state, (States.old_state_id == old_state.state_id))
            # The below filter, removes state change events that do not have
            # and old_state, new_state, or the old and
            # new state are the same for v8 schema or later.
            #
            # If the events/states were stored before v8 schema, we relay on the
            # prev_states dict to remove them.
            #
            # When all data is schema v8 or later, the check for EMPTY_JSON_OBJECT
            # can be removed.
            .filter(
                (Events.event_type != EVENT_STATE_CHANGED)
                | (Events.event_data != EMPTY_JSON_OBJECT)
                | (
                    (States.state_id.isnot(None))
                    & (old_state.state_id.isnot(None))
                    & (States.state != old_state.state)
                )
            )
            #
            # Prefilter out continuous domains that have
            # ATTR_UNIT_OF_MEASUREMENT as its much faster in sql.
            #
            .filter(
                (Events.event_type != EVENT_STATE_CHANGED)
                | sqlalchemy.not_(States.domain.in_(CONTINUOUS_DOMAINS))
                | sqlalchemy.not_(States.attributes.contains(UNIT_OF_MEASUREMENT_JSON))
            )
            .filter(
                Events.event_type.in_(ALL_EVENT_TYPES + list(hass.data.get(DOMAIN, {})))
            )
            .filter((Events.time_fired > start_day) & (Events.time_fired < end_day))
        )

        if entity_ids:
            query = query.filter(
                (
                    (States.last_updated == States.last_changed)
                    & States.entity_id.in_(entity_ids)
                )
                | (States.state_id.is_(None))
            )
        else:
            query = query.filter(
                (States.last_updated == States.last_changed)
                | (States.state_id.is_(None))
            )

        if apply_sql_entities_filter and filters:
            entity_filter = filters.entity_filter()
            if entity_filter is not None:
                query = query.filter(
                    entity_filter | (Events.event_type != EVENT_STATE_CHANGED)
                )

        # When all data is schema v8 or later, prev_states can be removed
        prev_states = {}
        return list(humanify(hass, yield_events(query), entity_attr_cache, prev_states))


def _keep_event(hass, event, entities_filter, entity_attr_cache):
    if event.event_type == EVENT_STATE_CHANGED:
        entity_id = event.entity_id
        if entity_id is None:
            return False

        # Do not report on new entities
        # Do not report on entity removal
        if not event.has_old_and_new_state:
            return False
    elif event.event_type in HOMEASSISTANT_EVENTS:
        entity_id = f"{HA_DOMAIN}."
    elif event.event_type in hass.data[DOMAIN] and ATTR_ENTITY_ID not in event.data:
        # If the entity_id isn't described, use the domain that describes
        # the event for filtering.
        domain = hass.data[DOMAIN][event.event_type][0]
        if domain is None:
            return False
        entity_id = f"{domain}."
    else:
        event_data = event.data
        entity_id = event_data.get(ATTR_ENTITY_ID)
        if entity_id is None:
            domain = event_data.get(ATTR_DOMAIN)
            if domain is None:
                return False
            entity_id = f"{domain}."

    return entities_filter is None or entities_filter(entity_id)


def _entry_message_from_event(hass, entity_id, domain, event, entity_attr_cache):
    """Convert a state to a message for the logbook."""
    # We pass domain in so we don't have to split entity_id again
    state_state = event.state

    if domain in ["device_tracker", "person"]:
        if state_state == STATE_NOT_HOME:
            return "is away"
        return f"is at {state_state}"

    if domain == "sun":
        if state_state == sun.STATE_ABOVE_HORIZON:
            return "has risen"
        return "has set"

    if domain == "binary_sensor":
        device_class = entity_attr_cache.get(entity_id, ATTR_DEVICE_CLASS, event)
        if device_class == "battery":
            if state_state == STATE_ON:
                return "is low"
            if state_state == STATE_OFF:
                return "is normal"

        if device_class == "connectivity":
            if state_state == STATE_ON:
                return "is connected"
            if state_state == STATE_OFF:
                return "is disconnected"

        if device_class in ["door", "garage_door", "opening", "window"]:
            if state_state == STATE_ON:
                return "is opened"
            if state_state == STATE_OFF:
                return "is closed"

        if device_class == "lock":
            if state_state == STATE_ON:
                return "is unlocked"
            if state_state == STATE_OFF:
                return "is locked"

        if device_class == "plug":
            if state_state == STATE_ON:
                return "is plugged in"
            if state_state == STATE_OFF:
                return "is unplugged"

        if device_class == "presence":
            if state_state == STATE_ON:
                return "is at home"
            if state_state == STATE_OFF:
                return "is away"

        if device_class == "safety":
            if state_state == STATE_ON:
                return "is unsafe"
            if state_state == STATE_OFF:
                return "is safe"

        if device_class in [
            "cold",
            "gas",
            "heat",
            "light",
            "moisture",
            "motion",
            "occupancy",
            "power",
            "problem",
            "smoke",
            "sound",
            "vibration",
        ]:
            if state_state == STATE_ON:
                return f"detected {device_class}"
            if state_state == STATE_OFF:
                return f"cleared (no {device_class} detected)"

    if state_state == STATE_ON:
        # Future: combine groups and its entity entries ?
        return "turned on"

    if state_state == STATE_OFF:
        return "turned off"

    return f"changed to {state_state}"


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    __slots__ = [
        "_row",
        "_event_data",
        "_time_fired",
        "_time_fired_isoformat",
        "_attributes",
        "event_type",
        "entity_id",
        "state",
        "domain",
    ]

    def __init__(self, row):
        """Init the lazy event."""
        self._row = row
        self._event_data = None
        self._time_fired = None
        self._time_fired_isoformat = None
        self._attributes = None
        self.event_type = self._row.event_type
        self.entity_id = self._row.entity_id
        self.state = self._row.state
        self.domain = self._row.domain

    @property
    def context_user_id(self):
        """Context user id of event."""
        return self._row.context_user_id

    @property
    def attributes(self):
        """State attributes."""
        if not self._attributes:
            if (
                self._row.attributes is None
                or self._row.attributes == EMPTY_JSON_OBJECT
            ):
                self._attributes = {}
            else:
                self._attributes = json.loads(self._row.attributes)
        return self._attributes

    @property
    def data(self):
        """Event data."""
        if not self._event_data:
            if self._row.event_data == EMPTY_JSON_OBJECT:
                self._event_data = {}
            else:
                self._event_data = json.loads(self._row.event_data)
        return self._event_data

    @property
    def time_fired_minute(self):
        """Minute the event was fired not converted."""
        return self._row.time_fired.minute

    @property
    def time_fired(self):
        """Time event was fired in utc."""
        if not self._time_fired:
            self._time_fired = (
                process_timestamp(self._row.time_fired) or dt_util.utcnow()
            )
        return self._time_fired

    @property
    def time_fired_isoformat(self):
        """Time event was fired in utc isoformat."""
        if not self._time_fired_isoformat:
            if self._time_fired:
                self._time_fired_isoformat = self._time_fired.isoformat()
            else:
                self._time_fired_isoformat = process_timestamp_to_utc_isoformat(
                    self._row.time_fired or dt_util.utcnow()
                )
        return self._time_fired_isoformat

    @property
    def has_old_and_new_state(self):
        """Check the json data to see if new_state and old_state is present without decoding."""
        # Delete this check once all states are saved in the v8 schema
        # format or later (they have the old_state_id column).

        # New events in v8 schema format
        if self._row.event_data == EMPTY_JSON_OBJECT:
            return self._row.state_id is not None and self._row.old_state_id is not None

        # Old events not in v8 schema format
        return (
            '"old_state": {' in self._row.event_data
            and '"new_state": {' in self._row.event_data
        )


class EntityAttributeCache:
    """A cache to lookup static entity_id attribute.

    This class should not be used to lookup attributes
    that are expected to change state.
    """

    def __init__(self, hass):
        """Init the cache."""
        self._hass = hass
        self._cache = {}

    def get(self, entity_id, attribute, event):
        """Lookup an attribute for an entity or get it from the cache."""
        if entity_id in self._cache:
            if attribute in self._cache[entity_id]:
                return self._cache[entity_id][attribute]
        else:
            self._cache[entity_id] = {}

        current_state = self._hass.states.get(entity_id)
        if current_state:
            # Try the current state as its faster than decoding the
            # attributes
            self._cache[entity_id][attribute] = current_state.attributes.get(
                attribute, None
            )
        else:
            # If the entity has been removed, decode the attributes
            # instead
            self._cache[entity_id][attribute] = event.attributes.get(attribute)

        return self._cache[entity_id][attribute]
