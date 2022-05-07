"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from contextlib import suppress
from datetime import datetime as dt, timedelta
from http import HTTPStatus
from itertools import groupby
import json
import re
from typing import Any, cast

from aiohttp import web
import sqlalchemy
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import aliased
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal
import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.history import (
    Filters,
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.proximity import DOMAIN as PROXIMITY_DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    EventData,
    Events,
    StateAttributes,
    States,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.components.sensor import ATTR_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import (
    DOMAIN as HA_DOMAIN,
    Context,
    Event,
    HomeAssistant,
    ServiceCall,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import InvalidEntityFormatError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    EntityFilter,
    convert_include_exclude_filter,
    generate_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

ENTITY_ID_JSON_TEMPLATE = '%"entity_id":"{}"%'
FRIENDLY_NAME_JSON_EXTRACT = re.compile('"friendly_name": ?"([^"]+)"')
ENTITY_ID_JSON_EXTRACT = re.compile('"entity_id": ?"([^"]+)"')
DOMAIN_JSON_EXTRACT = re.compile('"domain": ?"([^"]+)"')
ICON_JSON_EXTRACT = re.compile('"icon": ?"([^"]+)"')
ATTR_MESSAGE = "message"

CONTINUOUS_DOMAINS = {PROXIMITY_DOMAIN, SENSOR_DOMAIN}
CONTINUOUS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in CONTINUOUS_DOMAINS]

DOMAIN = "logbook"

GROUP_BY_MINUTES = 15

EMPTY_JSON_OBJECT = "{}"
UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'
UNIT_OF_MEASUREMENT_JSON_LIKE = f"%{UNIT_OF_MEASUREMENT_JSON}%"
HA_DOMAIN_ENTITY_ID = f"{HA_DOMAIN}._"

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
    Events.event_type.label("event_type"),
    Events.event_data.label("event_data"),
    Events.time_fired.label("time_fired"),
    Events.context_id.label("context_id"),
    Events.context_user_id.label("context_user_id"),
    Events.context_parent_id.label("context_parent_id"),
]

STATE_COLUMNS = [
    States.state.label("state"),
    States.entity_id.label("entity_id"),
    States.attributes.label("attributes"),
    StateAttributes.shared_attrs.label("shared_attrs"),
]

EMPTY_STATE_COLUMNS = [
    literal(value=None, type_=sqlalchemy.String).label("state"),
    literal(value=None, type_=sqlalchemy.String).label("entity_id"),
    literal(value=None, type_=sqlalchemy.Text).label("attributes"),
    literal(value=None, type_=sqlalchemy.Text).label("shared_attrs"),
]

SCRIPT_AUTOMATION_EVENTS = {EVENT_AUTOMATION_TRIGGERED, EVENT_SCRIPT_STARTED}

LOG_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_DOMAIN): cv.slug,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    }
)


@bind_hass
def log_entry(
    hass: HomeAssistant,
    name: str,
    message: str,
    domain: str | None = None,
    entity_id: str | None = None,
    context: Context | None = None,
) -> None:
    """Add an entry to the logbook."""
    hass.add_job(async_log_entry, hass, name, message, domain, entity_id, context)


@callback
@bind_hass
def async_log_entry(
    hass: HomeAssistant,
    name: str,
    message: str,
    domain: str | None = None,
    entity_id: str | None = None,
    context: Context | None = None,
) -> None:
    """Add an entry to the logbook."""
    data = {ATTR_NAME: name, ATTR_MESSAGE: message}

    if domain is not None:
        data[ATTR_DOMAIN] = domain
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id
    hass.bus.async_fire(EVENT_LOGBOOK_ENTRY, data, context=context)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Logbook setup."""
    hass.data[DOMAIN] = {}

    @callback
    def log_message(service: ServiceCall) -> None:
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

    frontend.async_register_built_in_panel(
        hass, "logbook", "logbook", "hass:format-list-bulleted-type"
    )

    if conf := config.get(DOMAIN, {}):
        filters = sqlalchemy_filter_from_include_exclude_conf(conf)
        entities_filter = convert_include_exclude_filter(conf)
    else:
        filters = None
        entities_filter = None

    hass.http.register_view(LogbookView(conf, filters, entities_filter))

    hass.services.async_register(DOMAIN, "log", log_message, schema=LOG_MESSAGE_SCHEMA)

    await async_process_integration_platforms(hass, DOMAIN, _process_logbook_platform)

    return True


async def _process_logbook_platform(
    hass: HomeAssistant, domain: str, platform: Any
) -> None:
    """Process a logbook platform."""

    @callback
    def _async_describe_event(
        domain: str,
        event_name: str,
        describe_callback: Callable[[Event], dict[str, Any]],
    ) -> None:
        """Teach logbook how to describe a new event."""
        hass.data[DOMAIN][event_name] = (domain, describe_callback)

    platform.async_describe_events(hass, _async_describe_event)


class LogbookView(HomeAssistantView):
    """Handle logbook view requests."""

    url = "/api/logbook"
    name = "api:logbook"
    extra_urls = ["/api/logbook/{datetime}"]

    def __init__(
        self,
        config: dict[str, Any],
        filters: Filters | None,
        entities_filter: EntityFilter | None,
    ) -> None:
        """Initialize the logbook view."""
        self.config = config
        self.filters = filters
        self.entities_filter = entities_filter

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Retrieve logbook entries."""
        if datetime:
            if (datetime_dt := dt_util.parse_datetime(datetime)) is None:
                return self.json_message("Invalid datetime", HTTPStatus.BAD_REQUEST)
        else:
            datetime_dt = dt_util.start_of_local_day()

        if (period_str := request.query.get("period")) is None:
            period: int = 1
        else:
            period = int(period_str)

        if entity_ids_str := request.query.get("entity"):
            try:
                entity_ids = cv.entity_ids(entity_ids_str)
            except vol.Invalid:
                raise InvalidEntityFormatError(
                    f"Invalid entity id(s) encountered: {entity_ids_str}. "
                    "Format should be <domain>.<object_id>"
                ) from vol.Invalid
        else:
            entity_ids = None

        if (end_time_str := request.query.get("end_time")) is None:
            start_day = dt_util.as_utc(datetime_dt) - timedelta(days=period - 1)
            end_day = start_day + timedelta(days=period)
        else:
            start_day = datetime_dt
            if (end_day_dt := dt_util.parse_datetime(end_time_str)) is None:
                return self.json_message("Invalid end_time", HTTPStatus.BAD_REQUEST)
            end_day = end_day_dt

        hass = request.app["hass"]

        entity_matches_only = "entity_matches_only" in request.query
        context_id = request.query.get("context_id")

        if entity_ids and context_id:
            return self.json_message(
                "Can't combine entity with context_id", HTTPStatus.BAD_REQUEST
            )

        def json_events() -> web.Response:
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

        return cast(
            web.Response, await get_instance(hass).async_add_executor_job(json_events)
        )


def humanify(
    hass: HomeAssistant,
    rows: Generator[Row, None, None],
    entity_attr_cache: EntityAttributeCache,
    row_indexer: RowIndexer,
) -> Generator[dict[str, Any], None, None]:
    """Generate a converted list of events into Entry objects.

    Will try to group events if possible:
    - if Home Assistant stop and start happen in same minute call it restarted
    """
    external_events = hass.data.get(DOMAIN, {})
    # Continuous sensors, will be excluded from the logbook
    continuous_sensors = {}

    # Group events in batches of GROUP_BY_MINUTES
    for _, g_rows in groupby(
        rows, lambda row: row.time_fired.minute // GROUP_BY_MINUTES  # type: ignore[no-any-return]
    ):

        rows_batch = list(g_rows)

        # Group HA start/stop events
        # Maps minute of event to 1: stop, 2: stop + start
        start_stop_events = {}

        # Process events
        for row in rows_batch:
            if row.event_type == EVENT_STATE_CHANGED:
                entity_id = row.entity_id
                if (
                    entity_id in continuous_sensors
                    or split_entity_id(entity_id)[0] != SENSOR_DOMAIN
                ):
                    continue
                assert entity_id is not None
                continuous_sensors[entity_id] = _is_sensor_continuous(hass, entity_id)

            elif row.event_type == EVENT_HOMEASSISTANT_STOP:
                if row.time_fired.minute in start_stop_events:
                    continue

                start_stop_events[row.time_fired.minute] = 1

            elif row.event_type == EVENT_HOMEASSISTANT_START:
                if row.time_fired.minute not in start_stop_events:
                    continue

                start_stop_events[row.time_fired.minute] = 2

        # Yield entries
        for row in rows_batch:
            if row.event_type == EVENT_STATE_CHANGED:
                entity_id = row.entity_id
                assert entity_id is not None

                if continuous_sensors.get(entity_id):
                    # Skip continuous sensors
                    continue

                event = row_indexer.get_event(row)
                data = {
                    "when": event.time_fired_isoformat,
                    "name": _entity_name_from_event(
                        entity_id, event, entity_attr_cache
                    ),
                    "state": event.state,
                    "entity_id": entity_id,
                }

                if icon := event.attributes_icon:
                    data["icon"] = icon

                if event.context_user_id:
                    data["context_user_id"] = event.context_user_id

                _augment_data_with_context(
                    data,
                    entity_id,
                    event,
                    row_indexer,
                    entity_attr_cache,
                    external_events,
                )

                yield data

            elif row.event_type in external_events:
                event = row_indexer.get_event(row)
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
                    row_indexer,
                    entity_attr_cache,
                    external_events,
                )
                yield data

            elif row.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(row.time_fired.minute) == 2:
                    continue
                yield {
                    "when": process_timestamp_to_utc_isoformat(row.time_fired)
                    or dt_util.utcnow(),
                    "name": "Home Assistant",
                    "message": "started",
                    "domain": HA_DOMAIN,
                }

            elif row.event_type == EVENT_HOMEASSISTANT_STOP:
                if start_stop_events.get(row.time_fired.minute) == 2:
                    action = "restarted"
                else:
                    action = "stopped"

                yield {
                    "when": process_timestamp_to_utc_isoformat(row.time_fired)
                    or dt_util.utcnow(),
                    "name": "Home Assistant",
                    "message": action,
                    "domain": HA_DOMAIN,
                }

            elif row.event_type == EVENT_LOGBOOK_ENTRY:
                event = row_indexer.get_event(row)
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
                    row_indexer,
                    entity_attr_cache,
                    external_events,
                )

                yield data


def _get_events(
    hass: HomeAssistant,
    start_day: dt,
    end_day: dt,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    entities_filter: EntityFilter | Callable[[str], bool] | None = None,
    entity_matches_only: bool = False,
    context_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get events for a period of time."""
    assert not (
        entity_ids and context_id
    ), "can't pass in both entity_ids and context_id"

    entity_attr_cache = EntityAttributeCache(hass)
    event_data_cache: dict[str, dict[str, Any]] = {}
    row_indexer = RowIndexer(event_data_cache)
    context_id_cache = row_indexer.context_id_cache

    def yield_rows(query: Query) -> Generator[Row, None, None]:
        """Yield Events that are not filtered away."""
        for row in query.yield_per(1000):
            context_id_cache.setdefault(row.context_id, row)
            if row.event_type == EVENT_CALL_SERVICE:
                continue
            if row.event_type == EVENT_STATE_CHANGED or _keep_row(
                hass, row, entities_filter
            ):
                yield row

    if entity_ids is not None:
        entities_filter = generate_filter([], entity_ids, [], [])

    with session_scope(hass=hass) as session:
        old_state = aliased(States, name="old_state")
        query: Query
        query = _generate_events_query_without_states(session)
        query = _apply_event_time_filter(query, start_day, end_day)
        query = _apply_event_types_filter(
            hass, query, ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED
        )

        if entity_ids is not None:
            if entity_matches_only:
                # When entity_matches_only is provided, contexts and events that do not
                # contain the entity_ids are not included in the logbook response.
                query = _apply_event_entity_id_matchers(query, entity_ids)
            query = query.outerjoin(EventData, (Events.data_id == EventData.data_id))
            query = query.union_all(
                _generate_states_query(
                    session, start_day, end_day, old_state, entity_ids
                )
            )
        else:
            if context_id is not None:
                query = query.filter(Events.context_id == context_id)
            query = query.outerjoin(EventData, (Events.data_id == EventData.data_id))

            states_query = _generate_states_query(
                session, start_day, end_day, old_state, entity_ids
            )
            unions: list[Query] = []
            if context_id is not None:
                # Once all the old `state_changed` events
                # are gone from the database remove the
                # _generate_legacy_events_context_id_query
                unions.append(
                    _generate_legacy_events_context_id_query(
                        session, context_id, start_day, end_day
                    )
                )
                states_query = states_query.outerjoin(
                    Events, (States.event_id == Events.event_id)
                )
                states_query = states_query.filter(States.context_id == context_id)
            elif filters:
                states_query = states_query.filter(filters.entity_filter())  # type: ignore[no-untyped-call]
            unions.append(states_query)
            query = query.union_all(*unions)

        query = query.order_by(Events.time_fired)

        return list(humanify(hass, yield_rows(query), entity_attr_cache, row_indexer))


def _generate_events_query_without_data(session: Session) -> Query:
    return session.query(
        literal(value=EVENT_STATE_CHANGED, type_=sqlalchemy.String).label("event_type"),
        literal(value=None, type_=sqlalchemy.Text).label("event_data"),
        States.last_changed.label("time_fired"),
        States.context_id.label("context_id"),
        States.context_user_id.label("context_user_id"),
        States.context_parent_id.label("context_parent_id"),
        literal(value=None, type_=sqlalchemy.Text).label("shared_data"),
        *STATE_COLUMNS,
    )


def _generate_legacy_events_context_id_query(
    session: Session,
    context_id: str,
    start_day: dt,
    end_day: dt,
) -> Query:
    """Generate a legacy events context id query that also joins states."""
    # This can be removed once we no longer have event_ids in the states table
    legacy_context_id_query = session.query(
        *EVENT_COLUMNS,
        literal(value=None, type_=sqlalchemy.String).label("shared_data"),
        States.state,
        States.entity_id,
        States.attributes,
        StateAttributes.shared_attrs,
    )
    legacy_context_id_query = _apply_event_time_filter(
        legacy_context_id_query, start_day, end_day
    )
    return (
        legacy_context_id_query.filter(Events.context_id == context_id)
        .outerjoin(States, (Events.event_id == States.event_id))
        .filter(States.last_updated == States.last_changed)
        .filter(_not_continuous_entity_matcher())
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    )


def _generate_events_query_without_states(session: Session) -> Query:
    return session.query(
        *EVENT_COLUMNS, EventData.shared_data.label("shared_data"), *EMPTY_STATE_COLUMNS
    )


def _generate_states_query(
    session: Session,
    start_day: dt,
    end_day: dt,
    old_state: States,
    entity_ids: Iterable[str] | None,
) -> Query:
    query = (
        _generate_events_query_without_data(session)
        .outerjoin(old_state, (States.old_state_id == old_state.state_id))
        .filter(_missing_state_matcher(old_state))
        .filter(_not_continuous_entity_matcher())
        .filter((States.last_updated > start_day) & (States.last_updated < end_day))
        .filter(States.last_updated == States.last_changed)
    )
    if entity_ids:
        query = query.filter(States.entity_id.in_(entity_ids))
    return query.outerjoin(
        StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
    )


def _missing_state_matcher(old_state: States) -> Any:
    # The below removes state change events that do not have
    # and old_state or the old_state is missing (newly added entities)
    # or the new_state is missing (removed entities)
    return sqlalchemy.and_(
        old_state.state_id.isnot(None),
        (States.state != old_state.state),
        States.state.isnot(None),
    )


def _not_continuous_entity_matcher() -> Any:
    """Match non continuous entities."""
    return sqlalchemy.or_(
        _not_continuous_domain_matcher(),
        sqlalchemy.and_(
            _continuous_domain_matcher, _not_uom_attributes_matcher()
        ).self_group(),
    )


def _not_continuous_domain_matcher() -> Any:
    """Match not continuous domains."""
    return sqlalchemy.and_(
        *[
            ~States.entity_id.like(entity_domain)
            for entity_domain in CONTINUOUS_ENTITY_ID_LIKE
        ],
    ).self_group()


def _continuous_domain_matcher() -> Any:
    """Match continuous domains."""
    return sqlalchemy.or_(
        *[
            States.entity_id.like(entity_domain)
            for entity_domain in CONTINUOUS_ENTITY_ID_LIKE
        ],
    ).self_group()


def _not_uom_attributes_matcher() -> Any:
    """Prefilter ATTR_UNIT_OF_MEASUREMENT as its much faster in sql."""
    return ~StateAttributes.shared_attrs.like(
        UNIT_OF_MEASUREMENT_JSON_LIKE
    ) | ~States.attributes.like(UNIT_OF_MEASUREMENT_JSON_LIKE)


def _apply_event_time_filter(events_query: Query, start_day: dt, end_day: dt) -> Query:
    return events_query.filter(
        (Events.time_fired > start_day) & (Events.time_fired < end_day)
    )


def _apply_event_types_filter(
    hass: HomeAssistant, query: Query, event_types: list[str]
) -> Query:
    return query.filter(
        Events.event_type.in_(event_types + list(hass.data.get(DOMAIN, {})))
    )


def _apply_event_entity_id_matchers(
    events_query: Query, entity_ids: Iterable[str]
) -> Query:
    ors = []
    for entity_id in entity_ids:
        like = ENTITY_ID_JSON_TEMPLATE.format(entity_id)
        ors.append(Events.event_data.like(like))
        ors.append(EventData.shared_data.like(like))
    return events_query.filter(sqlalchemy.or_(*ors))


def _keep_row(
    hass: HomeAssistant,
    row: Row,
    entities_filter: EntityFilter | Callable[[str], bool] | None = None,
) -> bool:
    event_type = row.event_type
    if event_type in HOMEASSISTANT_EVENTS:
        return entities_filter is None or entities_filter(HA_DOMAIN_ENTITY_ID)

    if entity_id := _extact_entity_id_from_row(row):
        return entities_filter is None or entities_filter(entity_id)

    if event_type in hass.data[DOMAIN]:
        # If the entity_id isn't described, use the domain that describes
        # the event for filtering.
        domain = hass.data[DOMAIN][event_type][0]
    else:
        domain = _extact_domain_from_row(row)

    return domain is not None and (
        entities_filter is None or entities_filter(f"{domain}._")
    )


def _augment_data_with_context(
    data: dict[str, Any],
    entity_id: str | None,
    event: LazyEventPartialState,
    row_indexer: RowIndexer,
    entity_attr_cache: EntityAttributeCache,
    external_events: dict[
        str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
    ],
) -> None:
    if not (context_event := row_indexer.get_by_context_id(event.context_id)):
        return

    if event == context_event:
        # This is the first event with the given ID. Was it directly caused by
        # a parent event?
        if event.context_parent_id:
            context_event = row_indexer.get_by_context_id(event.context_parent_id)
        # Ensure the (parent) context_event exists and is not the root cause of
        # this log entry.
        if not context_event or event == context_event:
            return

    event_type = context_event.event_type

    # State change
    if context_entity_id := context_event.entity_id:
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

    if not entity_id or context_event == event:
        return

    if (attr_entity_id := context_event.data_entity_id) is None or (
        event_type in SCRIPT_AUTOMATION_EVENTS and attr_entity_id == entity_id
    ):
        return

    data["context_entity_id"] = attr_entity_id
    data["context_entity_id_name"] = _entity_name_from_event(
        attr_entity_id, context_event, entity_attr_cache
    )
    data["context_event_type"] = event_type

    if event_type in external_events:
        domain, describe_event = external_events[event_type]
        data["context_domain"] = domain
        if name := describe_event(context_event).get(ATTR_NAME):
            data["context_name"] = name


def _entity_name_from_event(
    entity_id: str,
    event: LazyEventPartialState,
    entity_attr_cache: EntityAttributeCache,
) -> str:
    """Extract the entity name from the event using the cache if possible."""
    return entity_attr_cache.get(
        entity_id, ATTR_FRIENDLY_NAME, event
    ) or split_entity_id(entity_id)[1].replace("_", " ")


def _is_sensor_continuous(
    hass: HomeAssistant,
    entity_id: str,
) -> bool:
    """Determine if a sensor is continuous by checking its state class.

    Sensors with a unit_of_measurement are also considered continuous, but are filtered
    already by the SQL query generated by _get_events
    """
    registry = er.async_get(hass)
    if not (entry := registry.async_get(entity_id)):
        # Entity not registered, so can't have a state class
        return False
    return (
        entry.capabilities is not None
        and entry.capabilities.get(ATTR_STATE_CLASS) is not None
    )


def _extact_entity_id_from_row(row: Row) -> str | None:
    """Extract an entity id from a event row."""
    result = ENTITY_ID_JSON_EXTRACT.search(row.shared_data or row.event_data or "")
    return result.group(1) if result else None


def _extact_domain_from_row(row: Row) -> str | None:
    """Extract an domain from a event row."""
    result = DOMAIN_JSON_EXTRACT.search(row.shared_data or row.event_data or "")
    return result.group(1) if result else None


class RowIndexer:
    """A class to index rows by context_id and convert them to LazyEventPartialState."""

    def __init__(self, event_data_cache: dict[str, dict[str, Any]]) -> None:
        """Init the linker."""
        self._event_data_cache = event_data_cache
        self.context_id_cache: dict[str | None, Row | None] = {None: None}
        self.event_cache: dict[Row, LazyEventPartialState] = {}

    def get_event(self, row: Row) -> LazyEventPartialState:
        """Get the event from the row."""
        if event := self.event_cache.get(row):
            return event
        event = self.event_cache[row] = LazyEventPartialState(
            row, self._event_data_cache
        )
        return event

    def get_by_context_id(self, context_id: str | None) -> LazyEventPartialState | None:
        """Get an event from the cache or create it from the row."""
        if (row := self.context_id_cache.get(context_id)) is not None:
            return self.get_event(row)
        return None


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
        "context_id",
        "context_user_id",
        "context_parent_id",
        "time_fired_minute",
        "_event_data_cache",
    ]

    def __init__(
        self,
        row: Row,
        event_data_cache: dict[str, dict[str, Any]],
    ) -> None:
        """Init the lazy event."""
        self._row = row
        self._event_data: dict[str, Any] | None = None
        self._time_fired_isoformat: dt | None = None
        self.event_type: str = self._row.event_type
        self.entity_id: str | None = self._row.entity_id
        self.state = self._row.state
        self.context_id: str | None = self._row.context_id
        self.context_user_id: str | None = self._row.context_user_id
        self.context_parent_id: str | None = self._row.context_parent_id
        self.time_fired_minute: int = self._row.time_fired.minute
        self._event_data_cache = event_data_cache

    @property
    def attributes_icon(self) -> str | None:
        """Extract the icon from the decoded attributes or json."""
        result = ICON_JSON_EXTRACT.search(
            self._row.shared_attrs or self._row.attributes or ""
        )
        return result.group(1) if result else None

    @property
    def data_entity_id(self) -> str | None:
        """Extract the entity id from the decoded data or json."""
        return _extact_entity_id_from_row(self._row)

    @property
    def attributes_friendly_name(self) -> str | None:
        """Extract the friendly name from the decoded attributes or json."""
        result = FRIENDLY_NAME_JSON_EXTRACT.search(
            self._row.shared_attrs or self._row.attributes or ""
        )
        return result.group(1) if result else None

    @property
    def data(self) -> dict[str, Any]:
        """Event data."""
        if self._event_data is None:
            source: str = self._row.shared_data or self._row.event_data
            if not source:
                self._event_data = {}
            elif event_data := self._event_data_cache.get(source):
                self._event_data = event_data
            else:
                self._event_data = self._event_data_cache[source] = cast(
                    dict[str, Any], json.loads(source)
                )
        return self._event_data

    @property
    def time_fired_isoformat(self) -> dt | None:
        """Time event was fired in utc isoformat."""
        if not self._time_fired_isoformat:
            self._time_fired_isoformat = (
                process_timestamp_to_utc_isoformat(self._row.time_fired)
                or dt_util.utcnow()
            )

        return self._time_fired_isoformat


class EntityAttributeCache:
    """A cache to lookup static entity_id attribute.

    This class should not be used to lookup attributes
    that are expected to change state.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the cache."""
        self._hass = hass
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, entity_id: str, attribute: str, event: LazyEventPartialState) -> Any:
        """Lookup an attribute for an entity or get it from the cache."""
        if entity_id in self._cache:
            if attribute in self._cache[entity_id]:
                return self._cache[entity_id][attribute]
        else:
            cache = self._cache[entity_id] = {}

        if current_state := self._hass.states.get(entity_id):
            # Try the current state as its faster than decoding the
            # attributes
            cache[attribute] = current_state.attributes.get(attribute)
        else:
            # If the entity has been removed, decode the attributes
            # instead
            if attribute != ATTR_FRIENDLY_NAME:
                raise ValueError(
                    f"{attribute} is not supported by {self.__class__.__name__}"
                )
            cache[attribute] = event.attributes_friendly_name

        return cache[attribute]
