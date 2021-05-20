"""Event parser and human readable log generator."""
from contextlib import suppress
from datetime import timedelta
from itertools import groupby
import json
import re

import sqlalchemy
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import literal
import voluptuous as vol

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.history import sqlalchemy_filter_from_include_exclude_conf
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder.models import (
    Events,
    States,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    HTTP_BAD_REQUEST,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback, split_entity_id
from homeassistant.exceptions import InvalidEntityFormatError
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

ENTITY_ID_JSON_TEMPLATE = '"entity_id": "{}"'
ENTITY_ID_JSON_EXTRACT = re.compile('"entity_id": "([^"]+)"')
DOMAIN_JSON_EXTRACT = re.compile('"domain": "([^"]+)"')
ICON_JSON_EXTRACT = re.compile('"icon": "([^"]+)"')

ATTR_MESSAGE = "message"

CONTINUOUS_DOMAINS = ["proximity", "sensor"]

DOMAIN = "logbook"

GROUP_BY_MINUTES = 15

EMPTY_JSON_OBJECT = "{}"
UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'

HA_DOMAIN_ENTITY_ID = f"{HA_DOMAIN}."

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA}, extra=vol.ALLOW_EXTRA
)

HOMEASSISTANT_EVENTS = [
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
]

ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED = [
    EVENT_LOGBOOK_ENTRY,
    EVENT_CALL_SERVICE,
    *HOMEASSISTANT_EVENTS,
]

ALL_EVENT_TYPES = [
    EVENT_STATE_CHANGED,
    *ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED,
]

EVENT_COLUMNS = [
    Events.event_type,
    Events.event_data,
    Events.time_fired,
    Events.context_id,
    Events.context_user_id,
    Events.context_parent_id,
]

SCRIPT_AUTOMATION_EVENTS = [EVENT_AUTOMATION_TRIGGERED, EVENT_SCRIPT_STARTED]

LOG_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_DOMAIN): cv.slug,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@bind_hass
def log_entry(hass, name, message, domain=None, entity_id=None, context=None):
    """Add an entry to the logbook."""
    hass.add_job(async_log_entry, hass, name, message, domain, entity_id, context)


@bind_hass
def async_log_entry(hass, name, message, domain=None, entity_id=None, context=None):
    """Add an entry to the logbook."""
    data = {ATTR_NAME: name, ATTR_MESSAGE: message}

    if domain is not None:
        data[ATTR_DOMAIN] = domain
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id
    hass.bus.async_fire(EVENT_LOGBOOK_ENTRY, data, context=context)


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
        message = message.async_render(parse_result=False)
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

        entity_ids = request.query.get("entity")
        if entity_ids:
            try:
                entity_ids = cv.entity_ids(entity_ids)
            except vol.Invalid:
                raise InvalidEntityFormatError(
                    f"Invalid entity id(s) encountered: {entity_ids}. "
                    "Format should be <domain>.<object_id>"
                ) from vol.Invalid

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

        entity_matches_only = "entity_matches_only" in request.query
        context_id = request.query.get("context_id")

        if entity_ids and context_id:
            return self.json_message(
                "Can't combine entity with context_id", HTTP_BAD_REQUEST
            )

        def json_events():
            """Fetch events and generate JSON."""
            return self.json(
                _get_events(
                    hass,
                    start_day,
                    end_day,
                    entity_ids,
                    self.filters,
                    self.entities_filter,
                    entity_matches_only,
                    context_id,
                )
            )

        return await hass.async_add_executor_job(json_events)


def humanify(hass, events, entity_attr_cache, context_lookup):
    """Generate a converted list of events into Entry objects.

    Will try to group events if possible:
    - if 2+ sensor updates in GROUP_BY_MINUTES, show last
    - if Home Assistant stop and start happen in same minute call it restarted
    """
    external_events = hass.data.get(DOMAIN, {})

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
        for event in events_batch:
            if event.event_type == EVENT_STATE_CHANGED:
                entity_id = event.entity_id
                domain = event.domain

                if (
                    domain in CONTINUOUS_DOMAINS
                    and event != last_sensor_event[entity_id]
                ):
                    # Skip all but the last sensor state
                    continue

                data = {
                    "when": event.time_fired_isoformat,
                    "name": _entity_name_from_event(
                        entity_id, event, entity_attr_cache
                    ),
                    "state": event.state,
                    "entity_id": entity_id,
                }

                icon = event.attributes_icon
                if icon:
                    data["icon"] = icon

                if event.context_user_id:
                    data["context_user_id"] = event.context_user_id

                _augment_data_with_context(
                    data,
                    entity_id,
                    event,
                    context_lookup,
                    entity_attr_cache,
                    external_events,
                )

                yield data

            elif event.event_type in external_events:
                domain, describe_event = external_events[event.event_type]
                data = describe_event(event)
                data["when"] = event.time_fired_isoformat
                data["domain"] = domain
                if event.context_user_id:
                    data["context_user_id"] = event.context_user_id

                _augment_data_with_context(
                    data,
                    data.get(ATTR_ENTITY_ID),
                    event,
                    context_lookup,
                    entity_attr_cache,
                    external_events,
                )
                yield data

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(event.time_fired_minute) == 2:
                    continue

                yield {
                    "when": event.time_fired_isoformat,
                    "name": "Home Assistant",
                    "message": "started",
                    "domain": HA_DOMAIN,
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
                }

            elif event.event_type == EVENT_LOGBOOK_ENTRY:
                event_data = event.data
                domain = event_data.get(ATTR_DOMAIN)
                entity_id = event_data.get(ATTR_ENTITY_ID)
                if domain is None and entity_id is not None:
                    with suppress(IndexError):
                        domain = split_entity_id(str(entity_id))[0]

                data = {
                    "when": event.time_fired_isoformat,
                    "name": event_data.get(ATTR_NAME),
                    "message": event_data.get(ATTR_MESSAGE),
                    "domain": domain,
                    "entity_id": entity_id,
                }

                if event.context_user_id:
                    data["context_user_id"] = event.context_user_id

                _augment_data_with_context(
                    data,
                    entity_id,
                    event,
                    context_lookup,
                    entity_attr_cache,
                    external_events,
                )

                yield data


def _get_events(
    hass,
    start_day,
    end_day,
    entity_ids=None,
    filters=None,
    entities_filter=None,
    entity_matches_only=False,
    context_id=None,
):
    """Get events for a period of time."""
    assert not (
        entity_ids and context_id
    ), "can't pass in both entity_ids and context_id"

    entity_attr_cache = EntityAttributeCache(hass)
    context_lookup = {None: None}

    def yield_events(query):
        """Yield Events that are not filtered away."""
        for row in query.yield_per(1000):
            event = LazyEventPartialState(row)
            context_lookup.setdefault(event.context_id, event)
            if event.event_type == EVENT_CALL_SERVICE:
                continue
            if event.event_type == EVENT_STATE_CHANGED or _keep_event(
                hass, event, entities_filter
            ):
                yield event

    if entity_ids is not None:
        entities_filter = generate_filter([], entity_ids, [], [])

    with session_scope(hass=hass) as session:
        old_state = aliased(States, name="old_state")

        if entity_ids is not None:
            query = _generate_events_query_without_states(session)
            query = _apply_event_time_filter(query, start_day, end_day)
            query = _apply_event_types_filter(
                hass, query, ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED
            )
            if entity_matches_only:
                # When entity_matches_only is provided, contexts and events that do not
                # contain the entity_ids are not included in the logbook response.
                query = _apply_event_entity_id_matchers(query, entity_ids)

            query = query.union_all(
                _generate_states_query(
                    session, start_day, end_day, old_state, entity_ids
                )
            )
        else:
            query = _generate_events_query(session)
            query = _apply_event_time_filter(query, start_day, end_day)
            query = _apply_events_types_and_states_filter(
                hass, query, old_state
            ).filter(
                (States.last_updated == States.last_changed)
                | (Events.event_type != EVENT_STATE_CHANGED)
            )
            if filters:
                query = query.filter(
                    filters.entity_filter() | (Events.event_type != EVENT_STATE_CHANGED)
                )

            if context_id is not None:
                query = query.filter(Events.context_id == context_id)

        query = query.order_by(Events.time_fired)

        return list(
            humanify(hass, yield_events(query), entity_attr_cache, context_lookup)
        )


def _generate_events_query(session):
    return session.query(
        *EVENT_COLUMNS,
        States.state,
        States.entity_id,
        States.domain,
        States.attributes,
    )


def _generate_events_query_without_states(session):
    return session.query(
        *EVENT_COLUMNS,
        literal(value=None, type_=sqlalchemy.String).label("state"),
        literal(value=None, type_=sqlalchemy.String).label("entity_id"),
        literal(value=None, type_=sqlalchemy.String).label("domain"),
        literal(value=None, type_=sqlalchemy.Text).label("attributes"),
    )


def _generate_states_query(session, start_day, end_day, old_state, entity_ids):
    return (
        _generate_events_query(session)
        .outerjoin(Events, (States.event_id == Events.event_id))
        .outerjoin(old_state, (States.old_state_id == old_state.state_id))
        .filter(_missing_state_matcher(old_state))
        .filter(_continuous_entity_matcher())
        .filter((States.last_updated > start_day) & (States.last_updated < end_day))
        .filter(
            (States.last_updated == States.last_changed)
            & States.entity_id.in_(entity_ids)
        )
    )


def _apply_events_types_and_states_filter(hass, query, old_state):
    events_query = (
        query.outerjoin(States, (Events.event_id == States.event_id))
        .outerjoin(old_state, (States.old_state_id == old_state.state_id))
        .filter(
            (Events.event_type != EVENT_STATE_CHANGED)
            | _missing_state_matcher(old_state)
        )
        .filter(
            (Events.event_type != EVENT_STATE_CHANGED) | _continuous_entity_matcher()
        )
    )
    return _apply_event_types_filter(hass, events_query, ALL_EVENT_TYPES)


def _missing_state_matcher(old_state):
    # The below removes state change events that do not have
    # and old_state or the old_state is missing (newly added entities)
    # or the new_state is missing (removed entities)
    return sqlalchemy.and_(
        old_state.state_id.isnot(None),
        (States.state != old_state.state),
        States.state.isnot(None),
    )


def _continuous_entity_matcher():
    #
    # Prefilter out continuous domains that have
    # ATTR_UNIT_OF_MEASUREMENT as its much faster in sql.
    #
    return sqlalchemy.or_(
        sqlalchemy.not_(States.domain.in_(CONTINUOUS_DOMAINS)),
        sqlalchemy.not_(States.attributes.contains(UNIT_OF_MEASUREMENT_JSON)),
    )


def _apply_event_time_filter(events_query, start_day, end_day):
    return events_query.filter(
        (Events.time_fired > start_day) & (Events.time_fired < end_day)
    )


def _apply_event_types_filter(hass, query, event_types):
    return query.filter(
        Events.event_type.in_(event_types + list(hass.data.get(DOMAIN, {})))
    )


def _apply_event_entity_id_matchers(events_query, entity_ids):
    return events_query.filter(
        sqlalchemy.or_(
            *[
                Events.event_data.contains(ENTITY_ID_JSON_TEMPLATE.format(entity_id))
                for entity_id in entity_ids
            ]
        )
    )


def _keep_event(hass, event, entities_filter):
    if event.event_type in HOMEASSISTANT_EVENTS:
        return entities_filter is None or entities_filter(HA_DOMAIN_ENTITY_ID)

    entity_id = event.data_entity_id
    if entity_id:
        return entities_filter is None or entities_filter(entity_id)

    if event.event_type in hass.data[DOMAIN]:
        # If the entity_id isn't described, use the domain that describes
        # the event for filtering.
        domain = hass.data[DOMAIN][event.event_type][0]
    else:
        domain = event.data_domain

    if domain is None:
        return False

    return entities_filter is None or entities_filter(f"{domain}.")


def _augment_data_with_context(
    data, entity_id, event, context_lookup, entity_attr_cache, external_events
):
    context_event = context_lookup.get(event.context_id)

    if not context_event:
        return

    if event == context_event:
        # This is the first event with the given ID. Was it directly caused by
        # a parent event?
        if event.context_parent_id:
            context_event = context_lookup.get(event.context_parent_id)
        # Ensure the (parent) context_event exists and is not the root cause of
        # this log entry.
        if not context_event or event == context_event:
            return

    event_type = context_event.event_type
    context_entity_id = context_event.entity_id

    # State change
    if context_entity_id:
        data["context_entity_id"] = context_entity_id
        data["context_entity_id_name"] = _entity_name_from_event(
            context_entity_id, context_event, entity_attr_cache
        )
        data["context_event_type"] = event_type
        return

    event_data = context_event.data

    # Call service
    if event_type == EVENT_CALL_SERVICE:
        event_data = context_event.data
        data["context_domain"] = event_data.get(ATTR_DOMAIN)
        data["context_service"] = event_data.get(ATTR_SERVICE)
        data["context_event_type"] = event_type
        return

    if not entity_id:
        return

    attr_entity_id = event_data.get(ATTR_ENTITY_ID)
    if not isinstance(attr_entity_id, str) or (
        event_type in SCRIPT_AUTOMATION_EVENTS and attr_entity_id == entity_id
    ):
        return

    if context_event == event:
        return

    data["context_entity_id"] = attr_entity_id
    data["context_entity_id_name"] = _entity_name_from_event(
        attr_entity_id, context_event, entity_attr_cache
    )
    data["context_event_type"] = event_type

    if event_type in external_events:
        domain, describe_event = external_events[event_type]
        data["context_domain"] = domain
        name = describe_event(context_event).get(ATTR_NAME)
        if name:
            data["context_name"] = name


def _entity_name_from_event(entity_id, event, entity_attr_cache):
    """Extract the entity name from the event using the cache if possible."""
    return entity_attr_cache.get(
        entity_id, ATTR_FRIENDLY_NAME, event
    ) or split_entity_id(entity_id)[1].replace("_", " ")


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    __slots__ = [
        "_row",
        "_event_data",
        "_time_fired_isoformat",
        "_attributes",
        "event_type",
        "entity_id",
        "state",
        "domain",
        "context_id",
        "context_user_id",
        "context_parent_id",
        "time_fired_minute",
    ]

    def __init__(self, row):
        """Init the lazy event."""
        self._row = row
        self._event_data = None
        self._time_fired_isoformat = None
        self._attributes = None
        self.event_type = self._row.event_type
        self.entity_id = self._row.entity_id
        self.state = self._row.state
        self.domain = self._row.domain
        self.context_id = self._row.context_id
        self.context_user_id = self._row.context_user_id
        self.context_parent_id = self._row.context_parent_id
        self.time_fired_minute = self._row.time_fired.minute

    @property
    def attributes_icon(self):
        """Extract the icon from the decoded attributes or json."""
        if self._attributes:
            return self._attributes.get(ATTR_ICON)

        result = ICON_JSON_EXTRACT.search(self._row.attributes)
        return result and result.group(1)

    @property
    def data_entity_id(self):
        """Extract the entity id from the decoded data or json."""
        if self._event_data:
            return self._event_data.get(ATTR_ENTITY_ID)

        result = ENTITY_ID_JSON_EXTRACT.search(self._row.event_data)
        return result and result.group(1)

    @property
    def data_domain(self):
        """Extract the domain from the decoded data or json."""
        if self._event_data:
            return self._event_data.get(ATTR_DOMAIN)

        result = DOMAIN_JSON_EXTRACT.search(self._row.event_data)
        return result and result.group(1)

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
    def time_fired_isoformat(self):
        """Time event was fired in utc isoformat."""
        if not self._time_fired_isoformat:
            self._time_fired_isoformat = process_timestamp_to_utc_isoformat(
                self._row.time_fired or dt_util.utcnow()
            )

        return self._time_fired_isoformat


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
            self._cache[entity_id][attribute] = current_state.attributes.get(attribute)
        else:
            # If the entity has been removed, decode the attributes
            # instead
            self._cache[entity_id][attribute] = event.attributes.get(attribute)

        return self._cache[entity_id][attribute]
