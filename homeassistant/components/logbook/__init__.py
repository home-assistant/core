"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from contextlib import suppress
from datetime import datetime as dt, timedelta
from http import HTTPStatus
import json
import re
from typing import Any, cast

from aiohttp import web
import sqlalchemy
from sqlalchemy import lambda_stmt, select
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import aliased
from sqlalchemy.orm.query import Query
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select
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


def _humanify(
    hass: HomeAssistant,
    rows: Generator[Row, None, None],
    entity_name_cache: EntityNameCache,
    event_cache: EventCache,
    context_augmenter: ContextAugmenter,
) -> Generator[dict[str, Any], None, None]:
    """Generate a converted list of events into Entry objects.

    Will try to group events if possible:
    - if Home Assistant stop and start happen in same minute call it restarted
    """
    external_events = hass.data.get(DOMAIN, {})
    # Continuous sensors, will be excluded from the logbook
    continuous_sensors: dict[str, bool] = {}

    # Process events
    for row in rows:
        event_type = row.event_type
        if event_type == EVENT_STATE_CHANGED:
            entity_id = row.entity_id
            assert entity_id is not None
            # Skip continuous sensors
            if (
                is_continuous := continuous_sensors.get(entity_id)
            ) is None and split_entity_id(entity_id)[0] == SENSOR_DOMAIN:
                is_continuous = _is_sensor_continuous(hass, entity_id)
                continuous_sensors[entity_id] = is_continuous
            if is_continuous:
                continue

            data = {
                "when": _row_time_fired_isoformat(row),
                "name": entity_name_cache.get(entity_id, row),
                "state": row.state,
                "entity_id": entity_id,
            }
            if icon := _row_attributes_extract(row, ICON_JSON_EXTRACT):
                data["icon"] = icon

            context_augmenter.augment(data, entity_id, row)
            yield data

        elif event_type in external_events:
            domain, describe_event = external_events[event_type]
            data = describe_event(event_cache.get(row))
            data["when"] = _row_time_fired_isoformat(row)
            data["domain"] = domain
            context_augmenter.augment(data, data.get(ATTR_ENTITY_ID), row)
            yield data

        elif event_type == EVENT_HOMEASSISTANT_START:
            yield {
                "when": _row_time_fired_isoformat(row),
                "name": "Home Assistant",
                "message": "started",
                "domain": HA_DOMAIN,
            }
        elif event_type == EVENT_HOMEASSISTANT_STOP:
            yield {
                "when": _row_time_fired_isoformat(row),
                "name": "Home Assistant",
                "message": "stopped",
                "domain": HA_DOMAIN,
            }

        elif event_type == EVENT_LOGBOOK_ENTRY:
            event = event_cache.get(row)
            event_data = event.data
            domain = event_data.get(ATTR_DOMAIN)
            entity_id = event_data.get(ATTR_ENTITY_ID)
            if domain is None and entity_id is not None:
                with suppress(IndexError):
                    domain = split_entity_id(str(entity_id))[0]

            data = {
                "when": _row_time_fired_isoformat(row),
                "name": event_data.get(ATTR_NAME),
                "message": event_data.get(ATTR_MESSAGE),
                "domain": domain,
                "entity_id": entity_id,
            }
            context_augmenter.augment(data, entity_id, row)
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

    entity_name_cache = EntityNameCache(hass)
    event_data_cache: dict[str, dict[str, Any]] = {}
    context_lookup: dict[str | None, Row | None] = {None: None}
    event_cache = EventCache(event_data_cache)
    external_events = hass.data.get(DOMAIN, {})
    context_augmenter = ContextAugmenter(
        context_lookup, entity_name_cache, external_events, event_cache
    )

    def yield_rows(query: Query) -> Generator[Row, None, None]:
        """Yield Events that are not filtered away."""
        if entity_ids or context_id:
            rows = query.all()
        else:
            rows = query.yield_per(1000)
        for row in rows:
            context_lookup.setdefault(row.context_id, row)
            event_type = row.event_type
            if event_type != EVENT_CALL_SERVICE and (
                event_type == EVENT_STATE_CHANGED
                or _keep_row(hass, event_type, row, entities_filter)
            ):
                yield row

    if entity_ids is not None:
        entities_filter = generate_filter([], entity_ids, [], [])

    event_types = [
        *ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED,
        *hass.data.get(DOMAIN, {}),
    ]
    entity_filter = None
    if entity_ids is None and filters:
        entity_filter = filters.entity_filter()  # type: ignore[no-untyped-call]
    stmt = _generate_logbook_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        entity_filter,
        entity_matches_only,
        context_id,
    )
    with session_scope(hass=hass) as session:
        return list(
            _humanify(
                hass,
                yield_rows(session.execute(stmt)),
                entity_name_cache,
                event_cache,
                context_augmenter,
            )
        )


def _generate_logbook_query(
    start_day: dt,
    end_day: dt,
    event_types: list[str],
    entity_ids: list[str] | None = None,
    entity_filter: Any | None = None,
    entity_matches_only: bool = False,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate a logbook query lambda_stmt."""
    stmt = lambda_stmt(
        lambda: _generate_events_query_without_states()
        .where((Events.time_fired > start_day) & (Events.time_fired < end_day))
        .where(Events.event_type.in_(event_types))
        .outerjoin(EventData, (Events.data_id == EventData.data_id))
    )
    if entity_ids is not None:
        if entity_matches_only:
            # When entity_matches_only is provided, contexts and events that do not
            # contain the entity_ids are not included in the logbook response.
            stmt.add_criteria(
                lambda s: s.where(_apply_event_entity_id_matchers(entity_ids)),
                track_on=entity_ids,
            )
        stmt += lambda s: s.union_all(
            _generate_states_query()
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id.in_(entity_ids))
        )
    else:
        if context_id is not None:
            # Once all the old `state_changed` events
            # are gone from the database remove the
            # union_all(_generate_legacy_events_context_id_query()....)
            stmt += lambda s: s.where(Events.context_id == context_id).union_all(
                _generate_legacy_events_context_id_query()
                .where((Events.time_fired > start_day) & (Events.time_fired < end_day))
                .where(Events.context_id == context_id),
                _generate_states_query()
                .where(
                    (States.last_updated > start_day) & (States.last_updated < end_day)
                )
                .outerjoin(Events, (States.event_id == Events.event_id))
                .where(States.context_id == context_id),
            )
        elif entity_filter is not None:
            stmt += lambda s: s.union_all(
                _generate_states_query()
                .where(
                    (States.last_updated > start_day) & (States.last_updated < end_day)
                )
                .where(entity_filter)
            )
        else:
            stmt += lambda s: s.union_all(
                _generate_states_query().where(
                    (States.last_updated > start_day) & (States.last_updated < end_day)
                )
            )

    stmt += lambda s: s.order_by(Events.time_fired)
    return stmt


def _generate_events_query_without_data() -> Select:
    return select(
        literal(value=EVENT_STATE_CHANGED, type_=sqlalchemy.String).label("event_type"),
        literal(value=None, type_=sqlalchemy.Text).label("event_data"),
        States.last_changed.label("time_fired"),
        States.context_id.label("context_id"),
        States.context_user_id.label("context_user_id"),
        States.context_parent_id.label("context_parent_id"),
        literal(value=None, type_=sqlalchemy.Text).label("shared_data"),
        *STATE_COLUMNS,
    )


def _generate_legacy_events_context_id_query() -> Select:
    """Generate a legacy events context id query that also joins states."""
    # This can be removed once we no longer have event_ids in the states table
    return (
        select(
            *EVENT_COLUMNS,
            literal(value=None, type_=sqlalchemy.String).label("shared_data"),
            States.state,
            States.entity_id,
            States.attributes,
            StateAttributes.shared_attrs,
        )
        .outerjoin(States, (Events.event_id == States.event_id))
        .where(States.last_updated == States.last_changed)
        .where(_not_continuous_entity_matcher())
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    )


def _generate_events_query_without_states() -> Select:
    return select(
        *EVENT_COLUMNS, EventData.shared_data.label("shared_data"), *EMPTY_STATE_COLUMNS
    )


def _generate_states_query() -> Select:
    old_state = aliased(States, name="old_state")
    return (
        _generate_events_query_without_data()
        .outerjoin(old_state, (States.old_state_id == old_state.state_id))
        .where(_missing_state_matcher(old_state))
        .where(_not_continuous_entity_matcher())
        .where(States.last_updated == States.last_changed)
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    )


def _missing_state_matcher(old_state: States) -> sqlalchemy.and_:
    # The below removes state change events that do not have
    # and old_state or the old_state is missing (newly added entities)
    # or the new_state is missing (removed entities)
    return sqlalchemy.and_(
        old_state.state_id.isnot(None),
        (States.state != old_state.state),
        States.state.isnot(None),
    )


def _not_continuous_entity_matcher() -> sqlalchemy.or_:
    """Match non continuous entities."""
    return sqlalchemy.or_(
        _not_continuous_domain_matcher(),
        sqlalchemy.and_(
            _continuous_domain_matcher, _not_uom_attributes_matcher()
        ).self_group(),
    )


def _not_continuous_domain_matcher() -> sqlalchemy.and_:
    """Match not continuous domains."""
    return sqlalchemy.and_(
        *[
            ~States.entity_id.like(entity_domain)
            for entity_domain in CONTINUOUS_ENTITY_ID_LIKE
        ],
    ).self_group()


def _continuous_domain_matcher() -> sqlalchemy.or_:
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


def _apply_event_entity_id_matchers(entity_ids: Iterable[str]) -> sqlalchemy.or_:
    """Create matchers for the entity_id in the event_data."""
    ors = []
    for entity_id in entity_ids:
        like = ENTITY_ID_JSON_TEMPLATE.format(entity_id)
        ors.append(Events.event_data.like(like))
        ors.append(EventData.shared_data.like(like))
    return sqlalchemy.or_(*ors)


def _keep_row(
    hass: HomeAssistant,
    event_type: str,
    row: Row,
    entities_filter: EntityFilter | Callable[[str], bool] | None = None,
) -> bool:
    if event_type in HOMEASSISTANT_EVENTS:
        return entities_filter is None or entities_filter(HA_DOMAIN_ENTITY_ID)

    if entity_id := _row_event_data_extract(row, ENTITY_ID_JSON_EXTRACT):
        return entities_filter is None or entities_filter(entity_id)

    if event_type in hass.data[DOMAIN]:
        # If the entity_id isn't described, use the domain that describes
        # the event for filtering.
        domain = hass.data[DOMAIN][event_type][0]
    else:
        domain = _row_event_data_extract(row, DOMAIN_JSON_EXTRACT)

    return domain is not None and (
        entities_filter is None or entities_filter(f"{domain}._")
    )


class ContextAugmenter:
    """Augment data with context trace."""

    def __init__(
        self,
        context_lookup: dict[str | None, Row | None],
        entity_name_cache: EntityNameCache,
        external_events: dict[
            str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
        ],
        event_cache: EventCache,
    ) -> None:
        """Init the augmenter."""
        self.context_lookup = context_lookup
        self.entity_name_cache = entity_name_cache
        self.external_events = external_events
        self.event_cache = event_cache

    def augment(self, data: dict[str, Any], entity_id: str | None, row: Row) -> None:
        """Augment data from the row and cache."""
        if context_user_id := row.context_user_id:
            data["context_user_id"] = context_user_id

        if not (context_row := self.context_lookup.get(row.context_id)):
            return

        if _rows_match(row, context_row):
            # This is the first event with the given ID. Was it directly caused by
            # a parent event?
            if (
                not row.context_parent_id
                or (context_row := self.context_lookup.get(row.context_parent_id))
                is None
            ):
                return
            # Ensure the (parent) context_event exists and is not the root cause of
            # this log entry.
            if _rows_match(row, context_row):
                return

        event_type = context_row.event_type

        # State change
        if context_entity_id := context_row.entity_id:
            data["context_entity_id"] = context_entity_id
            data["context_entity_id_name"] = self.entity_name_cache.get(
                context_entity_id, context_row
            )
            data["context_event_type"] = event_type
            return

        # Call service
        if event_type == EVENT_CALL_SERVICE:
            event = self.event_cache.get(context_row)
            event_data = event.data
            data["context_domain"] = event_data.get(ATTR_DOMAIN)
            data["context_service"] = event_data.get(ATTR_SERVICE)
            data["context_event_type"] = event_type
            return

        if not entity_id:
            return

        attr_entity_id = _row_event_data_extract(context_row, ENTITY_ID_JSON_EXTRACT)
        if attr_entity_id is None or (
            event_type in SCRIPT_AUTOMATION_EVENTS and attr_entity_id == entity_id
        ):
            return

        data["context_entity_id"] = attr_entity_id
        data["context_entity_id_name"] = self.entity_name_cache.get(
            attr_entity_id, context_row
        )
        data["context_event_type"] = event_type

        if event_type in self.external_events:
            domain, describe_event = self.external_events[event_type]
            data["context_domain"] = domain
            event = self.event_cache.get(context_row)
            if name := describe_event(event).get(ATTR_NAME):
                data["context_name"] = name


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


def _rows_match(row: Row, other_row: Row) -> bool:
    """Check of rows match by using the same method as Events __hash__."""
    return bool(
        row.event_type == other_row.event_type
        and row.context_id == other_row.context_id
        and row.time_fired == other_row.time_fired
    )


def _row_event_data_extract(row: Row, extractor: re.Pattern) -> str | None:
    """Extract from event_data row."""
    result = extractor.search(row.shared_data or row.event_data or "")
    return result.group(1) if result else None


def _row_attributes_extract(row: Row, extractor: re.Pattern) -> str | None:
    """Extract from attributes row."""
    result = extractor.search(row.shared_attrs or row.attributes or "")
    return result.group(1) if result else None


def _row_time_fired_isoformat(row: Row) -> dt | None:
    """Convert the row timed_fired to isoformat."""
    return process_timestamp_to_utc_isoformat(row.time_fired) or dt_util.utcnow()


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    __slots__ = [
        "row",
        "_event_data",
        "_event_data_cache",
        "event_type",
        "entity_id",
        "state",
        "context_id",
        "context_user_id",
        "context_parent_id",
        "data",
    ]

    def __init__(
        self,
        row: Row,
        event_data_cache: dict[str, dict[str, Any]],
    ) -> None:
        """Init the lazy event."""
        self.row = row
        self._event_data: dict[str, Any] | None = None
        self._event_data_cache = event_data_cache
        self.event_type: str = self.row.event_type
        self.entity_id: str | None = self.row.entity_id
        self.state = self.row.state
        self.context_id: str | None = self.row.context_id
        self.context_user_id: str | None = self.row.context_user_id
        self.context_parent_id: str | None = self.row.context_parent_id
        source: str = self.row.shared_data or self.row.event_data
        if not source:
            self.data = {}
        elif event_data := self._event_data_cache.get(source):
            self.data = event_data
        else:
            self.data = self._event_data_cache[source] = cast(
                dict[str, Any], json.loads(source)
            )


class EntityNameCache:
    """A cache to lookup the name for an entity.

    This class should not be used to lookup attributes
    that are expected to change state.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the cache."""
        self._hass = hass
        self._names: dict[str, str] = {}

    def get(self, entity_id: str, row: Row) -> str:
        """Lookup an the friendly name."""
        if entity_id in self._names:
            return self._names[entity_id]
        if (current_state := self._hass.states.get(entity_id)) and (
            friendly_name := current_state.attributes.get(ATTR_FRIENDLY_NAME)
        ):
            self._names[entity_id] = friendly_name
        elif extracted_name := _row_attributes_extract(row, FRIENDLY_NAME_JSON_EXTRACT):
            self._names[entity_id] = extracted_name
        else:
            return split_entity_id(entity_id)[1].replace("_", " ")

        return self._names[entity_id]


class EventCache:
    """Cache LazyEventPartialState by row."""

    def __init__(self, event_data_cache: dict[str, dict[str, Any]]) -> None:
        """Init the cache."""
        self._event_data_cache = event_data_cache
        self.event_cache: dict[Row, LazyEventPartialState] = {}

    def get(self, row: Row) -> LazyEventPartialState:
        """Get the event from the row."""
        if event := self.event_cache.get(row):
            return event
        event = self.event_cache[row] = LazyEventPartialState(
            row, self._event_data_cache
        )
        return event
