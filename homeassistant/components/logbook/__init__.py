"""Event parser and human readable log generator."""
from datetime import timedelta
from itertools import groupby
import json
import logging
import time

from sqlalchemy.exc import SQLAlchemyError
import voluptuous as vol

from homeassistant.components import sun
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder.models import Events, States, process_timestamp
from homeassistant.components.recorder.util import (
    QUERY_RETRY_WAIT,
    RETRIES,
    session_scope,
)
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_HIDDEN,
    ATTR_NAME,
    CONF_EXCLUDE,
    CONF_INCLUDE,
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
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_MESSAGE = "message"

CONF_DOMAINS = "domains"
CONF_ENTITIES = "entities"
CONTINUOUS_DOMAINS = ["proximity", "sensor"]

DOMAIN = "logbook"

GROUP_BY_MINUTES = 15

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                CONF_EXCLUDE: vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
                CONF_INCLUDE: vol.Schema(
                    {
                        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                        vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ALL_EVENT_TYPES = [
    EVENT_STATE_CHANGED,
    EVENT_LOGBOOK_ENTRY,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
]

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


@bind_hass
def async_describe_event(hass, domain, event_name, describe_callback):
    """Teach logbook how to describe a new event."""
    hass.data.setdefault(DOMAIN, {})[event_name] = (domain, describe_callback)


async def async_setup(hass, config):
    """Listen for download events to download files."""

    @callback
    def log_message(service):
        """Handle sending notification message service calls."""
        message = service.data[ATTR_MESSAGE]
        name = service.data[ATTR_NAME]
        domain = service.data.get(ATTR_DOMAIN)
        entity_id = service.data.get(ATTR_ENTITY_ID)

        message.hass = hass
        message = message.async_render()
        async_log_entry(hass, name, message, domain, entity_id)

    hass.http.register_view(LogbookView(config.get(DOMAIN, {})))

    hass.components.frontend.async_register_built_in_panel(
        "logbook", "logbook", "hass:format-list-bulleted-type"
    )

    hass.services.async_register(DOMAIN, "log", log_message, schema=LOG_MESSAGE_SCHEMA)
    return True


class LogbookView(HomeAssistantView):
    """Handle logbook view requests."""

    url = "/api/logbook"
    name = "api:logbook"
    extra_urls = ["/api/logbook/{datetime}"]

    def __init__(self, config):
        """Initialize the logbook view."""
        self.config = config

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
                _get_events(hass, self.config, start_day, end_day, entity_id)
            )

        return await hass.async_add_job(json_events)


def humanify(hass, events, prev_states=None):
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
                data["when"] = event.time_fired
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

                if domain in CONTINUOUS_DOMAINS:
                    # Skip all but the last sensor state
                    if event != last_sensor_event[entity_id]:
                        continue

                    # Don't show continuous sensor value changes in the logbook
                    if _get_attribute(hass, entity_id, event, "unit_of_measurement"):
                        continue

                name = _get_attribute(
                    hass, entity_id, event, ATTR_FRIENDLY_NAME
                ) or split_entity_id(entity_id)[1].replace("_", " ")

                yield {
                    "when": event.time_fired,
                    "name": name,
                    "message": _entry_message_from_event(
                        hass, entity_id, domain, event
                    ),
                    "domain": domain,
                    "entity_id": entity_id,
                    "context_user_id": event.context_user_id,
                }

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(event.time_fired_minute) == 2:
                    continue

                yield {
                    "when": event.time_fired,
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
                    "when": event.time_fired,
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
                    "when": event.time_fired,
                    "name": event_data.get(ATTR_NAME),
                    "message": event_data.get(ATTR_MESSAGE),
                    "domain": domain,
                    "entity_id": entity_id,
                }


def _get_related_entity_ids(session, entity_filter):
    timer_start = time.perf_counter()

    query = session.query(States).with_entities(States.entity_id).distinct()

    for tryno in range(RETRIES):
        try:
            result = [row.entity_id for row in query if entity_filter(row.entity_id)]

            if _LOGGER.isEnabledFor(logging.DEBUG):
                elapsed = time.perf_counter() - timer_start
                _LOGGER.debug(
                    "fetching %d distinct domain/entity_id pairs took %fs",
                    len(result),
                    elapsed,
                )

            return result
        except SQLAlchemyError as err:
            _LOGGER.error("Error executing query: %s", err)

            if tryno == RETRIES - 1:
                raise
            time.sleep(QUERY_RETRY_WAIT)


def _generate_filter_from_config(config):
    excluded_entities = []
    excluded_domains = []
    included_entities = []
    included_domains = []

    exclude = config.get(CONF_EXCLUDE)
    if exclude:
        excluded_entities = exclude.get(CONF_ENTITIES, [])
        excluded_domains = exclude.get(CONF_DOMAINS, [])
    include = config.get(CONF_INCLUDE)
    if include:
        included_entities = include.get(CONF_ENTITIES, [])
        included_domains = include.get(CONF_DOMAINS, [])

    return generate_filter(
        included_domains, included_entities, excluded_domains, excluded_entities
    )


def _get_events(hass, config, start_day, end_day, entity_id=None):
    """Get events for a period of time."""
    entities_filter = _generate_filter_from_config(config)

    def yield_events(query):
        """Yield Events that are not filtered away."""
        for row in query.yield_per(1000):
            event = LazyEventPartialState(row)
            if _keep_event(hass, event, entities_filter):
                yield event

    with session_scope(hass=hass) as session:
        if entity_id is not None:
            entity_ids = [entity_id.lower()]
        elif config.get(CONF_EXCLUDE) or config.get(CONF_INCLUDE):
            entity_ids = _get_related_entity_ids(session, entities_filter)
        else:
            entity_ids = None

        query = (
            session.query(
                Events.event_type,
                Events.event_data,
                Events.time_fired,
                Events.context_user_id,
                States.state,
                States.entity_id,
                States.domain,
            )
            .order_by(Events.time_fired)
            .outerjoin(States, (Events.event_id == States.event_id))
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

        prev_states = {}
        return list(humanify(hass, yield_events(query), prev_states))


def _get_attribute(hass, entity_id, event, attribute):
    current_state = hass.states.get(entity_id)
    if not current_state:
        return event.data.get("new_state", {}).get("attributes", {}).get(attribute)
    return current_state.attributes.get(attribute, None)


def _keep_event(hass, event, entities_filter):

    if event.event_type == EVENT_STATE_CHANGED:
        entity_id = event.entity_id
        if entity_id is None:
            return False

        # Do not report on new entities
        # Do not report on entity removal
        if not event.has_old_and_new_state:
            return False

        # exclude entities which are customized hidden
        if event.hidden:
            return False

    elif event.event_type == EVENT_LOGBOOK_ENTRY:
        event_data = event.data
        domain = event_data.get(ATTR_DOMAIN)
        entity_id = None
    elif event.event_type in hass.data.get(DOMAIN, {}) and not event.data.get(
        "entity_id"
    ):
        # If the entity_id isn't described, use the domain that describes
        # the event for filtering.
        domain = hass.data[DOMAIN][event.event_type][0]
        entity_id = None
    else:
        event_data = event.data
        domain = event_data.get(ATTR_DOMAIN)
        entity_id = event_data.get("entity_id")

    if not entity_id and domain:
        entity_id = f"{domain}."

    return not entity_id or entities_filter(entity_id)


def _entry_message_from_event(hass, entity_id, domain, event):
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
        device_class = _get_attribute(hass, entity_id, event, "device_class")
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
        self.event_type = self._row.event_type
        self.entity_id = self._row.entity_id
        self.state = self._row.state
        self.domain = self._row.domain

    @property
    def context_user_id(self):
        """Context user id of event."""
        return self._row.context_user_id

    @property
    def data(self):
        """Event data."""

        if not self._event_data:
            if self._row.event_data == "{}":
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
    def has_old_and_new_state(self):
        """Check the json data to see if new_state and old_state is present without decoding."""
        return (
            '"old_state": {' in self._row.event_data
            and '"new_state": {' in self._row.event_data
        )

    @property
    def hidden(self):
        """Check the json to see if hidden."""
        if '"hidden":' in self._row.event_data:
            return (
                self.data.get("new_state", {})
                .get("attributes", {})
                .get(ATTR_HIDDEN, False)
            )
        return False
