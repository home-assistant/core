"""Queries for logbook."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime as dt
import json
from typing import Any

import sqlalchemy
from sqlalchemy import JSON, Column, lambda_stmt, select, type_coerce, union_all
from sqlalchemy.orm import Query, aliased
from sqlalchemy.sql.elements import ClauseList
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.components.proximity import DOMAIN as PROXIMITY_DOMAIN
from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import (
    ENTITY_ID_LAST_UPDATED_INDEX,
    JSON_VARIENT_CAST,
    JSONB_VARIENT_CAST,
    LAST_UPDATED_INDEX,
    EventData,
    Events,
    StateAttributes,
    States,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

CONTINUOUS_DOMAINS = {PROXIMITY_DOMAIN, SENSOR_DOMAIN}
CONTINUOUS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in CONTINUOUS_DOMAINS]

UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'
UNIT_OF_MEASUREMENT_JSON_LIKE = f"%{UNIT_OF_MEASUREMENT_JSON}%"

OLD_STATE = aliased(States, name="old_state")


class JSONLiteral(JSON):  # type: ignore[misc]
    """Teach SA how to literalize json."""

    def literal_processor(self, dialect: str) -> Callable[[Any], str]:
        """Processor to convert a value to JSON."""

        def process(value: Any) -> str:
            """Dump json."""
            return json.dumps(value)

        return process


EVENT_DATA_JSON = type_coerce(
    EventData.shared_data.cast(JSONB_VARIENT_CAST), JSONLiteral(none_as_null=True)
)
OLD_FORMAT_EVENT_DATA_JSON = type_coerce(
    Events.event_data.cast(JSONB_VARIENT_CAST), JSONLiteral(none_as_null=True)
)

SHARED_ATTRS_JSON = type_coerce(
    StateAttributes.shared_attrs.cast(JSON_VARIENT_CAST), JSON(none_as_null=True)
)
OLD_FORMAT_ATTRS_JSON = type_coerce(
    States.attributes.cast(JSON_VARIENT_CAST), JSON(none_as_null=True)
)

ENTITY_ID_IN_EVENT: Column = EVENT_DATA_JSON["entity_id"]
OLD_ENTITY_ID_IN_EVENT: Column = OLD_FORMAT_EVENT_DATA_JSON["entity_id"]
DEVICE_ID_IN_EVENT: Column = EVENT_DATA_JSON["device_id"]

PSUEDO_EVENT_STATE_CHANGED = None
# Since we don't store event_types and None
# and we don't store state_changed in events
# we use a NULL for state_changed events
# when we synthesize them from the states table
# since it avoids another column being sent
# in the payload

EVENT_COLUMNS = (
    Events.event_id.label("event_id"),
    Events.event_type.label("event_type"),
    Events.event_data.label("event_data"),
    Events.time_fired.label("time_fired"),
    Events.context_id.label("context_id"),
    Events.context_user_id.label("context_user_id"),
    Events.context_parent_id.label("context_parent_id"),
)

STATE_COLUMNS = (
    States.state_id.label("state_id"),
    States.state.label("state"),
    States.entity_id.label("entity_id"),
    SHARED_ATTRS_JSON["icon"].as_string().label("icon"),
    OLD_FORMAT_ATTRS_JSON["icon"].as_string().label("old_format_icon"),
)

STATE_CONTEXT_ONLY_COLUMNS = (
    States.state_id.label("state_id"),
    States.state.label("state"),
    States.entity_id.label("entity_id"),
    literal(value=None, type_=sqlalchemy.String).label("icon"),
    literal(value=None, type_=sqlalchemy.String).label("old_format_icon"),
)

EVENT_COLUMNS_FOR_STATE_SELECT = [
    literal(value=None, type_=sqlalchemy.Text).label("event_id"),
    # We use PSUEDO_EVENT_STATE_CHANGED aka None for
    # state_changed events since it takes up less
    # space in the response and every row has to be
    # marked with the event_type
    literal(value=PSUEDO_EVENT_STATE_CHANGED, type_=sqlalchemy.String).label(
        "event_type"
    ),
    literal(value=None, type_=sqlalchemy.Text).label("event_data"),
    States.last_updated.label("time_fired"),
    States.context_id.label("context_id"),
    States.context_user_id.label("context_user_id"),
    States.context_parent_id.label("context_parent_id"),
    literal(value=None, type_=sqlalchemy.Text).label("shared_data"),
]

EMPTY_STATE_COLUMNS = (
    literal(value=None, type_=sqlalchemy.String).label("state_id"),
    literal(value=None, type_=sqlalchemy.String).label("state"),
    literal(value=None, type_=sqlalchemy.String).label("entity_id"),
    literal(value=None, type_=sqlalchemy.String).label("icon"),
    literal(value=None, type_=sqlalchemy.String).label("old_format_icon"),
)


EVENT_ROWS_NO_STATES = (
    *EVENT_COLUMNS,
    EventData.shared_data.label("shared_data"),
    *EMPTY_STATE_COLUMNS,
)

# Virtual column to tell logbook if it should avoid processing
# the event as its only used to link contexts
CONTEXT_ONLY = literal("1").label("context_only")
NOT_CONTEXT_ONLY = literal(None).label("context_only")


def statement_for_request(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str] | None = None,
    json_quotable_entity_ids: list[str] | None = None,
    device_ids: list[str] | None = None,
    json_quotable_device_ids: list[str] | None = None,
    filters: Filters | None = None,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate the logbook statement for a logbook request."""

    # No entities: logbook sends everything for the timeframe
    # limited by the context_id and the yaml configured filter
    if not entity_ids and not device_ids:
        entity_filter = filters.entity_filter() if filters else None
        return _all_stmt(start_day, end_day, event_types, entity_filter, context_id)

    # sqlalchemy caches object quoting, the
    # json quotable ones must be a different
    # object from the non-json ones to prevent
    # sqlalchemy from quoting them incorrectly
    assert not device_ids or (device_ids is not json_quotable_device_ids)
    assert not entity_ids or (entity_ids is not json_quotable_entity_ids)

    # Multiple entities: logbook sends everything for the timeframe for the entities and devices
    if entity_ids and device_ids:
        assert json_quotable_entity_ids is not None
        assert json_quotable_device_ids is not None
        return _entities_devices_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quotable_entity_ids,
            json_quotable_device_ids,
        )

    if entity_ids:
        assert json_quotable_entity_ids is not None
        return _entities_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quotable_entity_ids,
        )

    assert json_quotable_device_ids is not None
    return _devices_stmt(
        start_day,
        end_day,
        event_types,
        json_quotable_device_ids,
    )


def _select_events_context_id_subquery(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
) -> Select:
    """Generate the select for a context_id subquery."""
    return (
        select(Events.context_id)
        .where((Events.time_fired > start_day) & (Events.time_fired < end_day))
        .where(Events.event_type.in_(event_types))
        .outerjoin(EventData, (Events.data_id == EventData.data_id))
    )


def _select_entities_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple entities."""
    return select(
        union_all(
            _select_events_context_id_subquery(start_day, end_day, event_types).where(
                _apply_event_entity_id_matchers(json_quotable_entity_ids)
            ),
            _apply_entities_hints(select(States.context_id))
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id.in_(entity_ids)),
        ).c.context_id
    )


def _select_device_id_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple devices."""
    return select(
        union_all(
            _select_events_context_id_subquery(start_day, end_day, event_types).where(
                _apply_event_device_id_matchers(json_quotable_device_ids)
            ),
        ).c.context_id
    )


def _select_entities_device_id_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
    json_quotable_device_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple entities and multiple devices."""
    return select(
        union_all(
            _select_events_context_id_subquery(start_day, end_day, event_types).where(
                _apply_event_entity_id_device_id_matchers(
                    json_quotable_entity_ids, json_quotable_device_ids
                )
            ),
            _apply_entities_hints(select(States.context_id))
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id.in_(entity_ids)),
        ).c.context_id
    )


def _select_events_context_only() -> Select:
    """Generate an events query that mark them as for context_only.

    By marking them as context_only we know they are only for
    linking context ids and we can avoid processing them.
    """
    return select(*EVENT_ROWS_NO_STATES, CONTEXT_ONLY).outerjoin(
        EventData, (Events.data_id == EventData.data_id)
    )


def _select_states_context_only() -> Select:
    """Generate an states query that mark them as for context_only.

    By marking them as context_only we know they are only for
    linking context ids and we can avoid processing them.
    """
    return select(
        *EVENT_COLUMNS_FOR_STATE_SELECT, *STATE_CONTEXT_ONLY_COLUMNS, CONTEXT_ONLY
    )


def _apply_entities_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> StatementLambdaElement:
    """Generate a CTE to find the entity and device context ids and a query to find linked row."""
    entities_cte = _select_entities_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quotable_entity_ids,
    ).cte()
    return query.union_all(
        _states_query_for_entity_ids(start_day, end_day, entity_ids),
        _select_events_context_only().where(Events.context_id.in_(entities_cte)),
        _select_states_context_only()
        .where(States.entity_id.not_in(entity_ids))
        .where(States.context_id.in_(entities_cte)),
    )


def _entities_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
    )
    assert json_quotable_entity_ids is not None
    stmt += lambda s: _apply_entities_context_union(
        s.where(_apply_event_entity_id_matchers(json_quotable_entity_ids)),
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quotable_entity_ids,
    ).order_by(Events.time_fired)
    return stmt


def _apply_entities_devices_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    devices_entities_cte = _select_entities_device_id_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quotable_entity_ids,
        json_quotable_device_ids,
    ).cte()
    return query.union_all(
        _states_query_for_entity_ids(start_day, end_day, entity_ids),
        _select_events_context_only().where(
            Events.context_id.in_(devices_entities_cte)
        ),
        _select_states_context_only()
        .where(States.entity_id.not_in(entity_ids))
        .where(States.context_id.in_(devices_entities_cte)),
    )


def _entities_devices_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
    )
    stmt += lambda s: _apply_entities_devices_context_union(
        s.where(
            _apply_event_entity_id_device_id_matchers(
                json_quotable_entity_ids, json_quotable_device_ids
            )
        ),
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quotable_entity_ids,
        json_quotable_device_ids,
    ).order_by(Events.time_fired)
    return stmt


def _apply_devices_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a CTE to find the device context ids and a query to find linked row."""
    devices_cte = _select_device_id_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        json_quotable_device_ids,
    ).cte()
    return query.union_all(
        _select_events_context_only().where(Events.context_id.in_(devices_cte)),
        _select_states_context_only().where(States.context_id.in_(devices_cte)),
    )


def _devices_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str] | None,
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
    )
    assert json_quotable_device_ids is not None
    stmt += lambda s: _apply_devices_context_union(
        s.where(_apply_event_device_id_matchers(json_quotable_device_ids)),
        start_day,
        end_day,
        event_types,
        json_quotable_device_ids,
    ).order_by(Events.time_fired)
    return stmt


def _all_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_filter: ClauseList | None = None,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate a logbook query for all entities."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
    )
    if context_id is not None:
        # Once all the old `state_changed` events
        # are gone from the database remove the
        # _legacy_select_events_context_id()
        stmt += lambda s: s.where(Events.context_id == context_id).union_all(
            _states_query_for_context_id(start_day, end_day, context_id),
            _legacy_select_events_context_id(start_day, end_day, context_id),
        )
    elif entity_filter is not None:
        stmt += lambda s: s.union_all(
            _states_query_for_all(start_day, end_day).where(entity_filter)
        )
    else:
        stmt += lambda s: s.union_all(_states_query_for_all(start_day, end_day))
    stmt += lambda s: s.order_by(Events.time_fired)
    return stmt


def _legacy_select_events_context_id(
    start_day: dt, end_day: dt, context_id: str
) -> Select:
    """Generate a legacy events context id select that also joins states."""
    # This can be removed once we no longer have event_ids in the states table
    return (
        select(
            *EVENT_COLUMNS,
            literal(value=None, type_=sqlalchemy.String).label("shared_data"),
            *STATE_COLUMNS,
            NOT_CONTEXT_ONLY,
        )
        .outerjoin(States, (Events.event_id == States.event_id))
        .where(
            (States.last_updated == States.last_changed) | States.last_changed.is_(None)
        )
        .where(_not_continuous_entity_matcher())
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
        .where((Events.time_fired > start_day) & (Events.time_fired < end_day))
        .where(Events.context_id == context_id)
    )


def _select_events_without_states(
    start_day: dt, end_day: dt, event_types: tuple[str, ...]
) -> Select:
    """Generate an events select that does not join states."""
    return (
        select(*EVENT_ROWS_NO_STATES, NOT_CONTEXT_ONLY)
        .where((Events.time_fired > start_day) & (Events.time_fired < end_day))
        .where(Events.event_type.in_(event_types))
        .outerjoin(EventData, (Events.data_id == EventData.data_id))
    )


def _states_query_for_context_id(start_day: dt, end_day: dt, context_id: str) -> Query:
    return _apply_states_filters(_select_states(), start_day, end_day).where(
        States.context_id == context_id
    )


def _states_query_for_entity_ids(
    start_day: dt, end_day: dt, entity_ids: list[str]
) -> Query:
    return _apply_states_filters(
        _apply_entities_hints(_select_states()), start_day, end_day
    ).where(States.entity_id.in_(entity_ids))


def _states_query_for_all(start_day: dt, end_day: dt) -> Query:
    return _apply_states_filters(_apply_all_hints(_select_states()), start_day, end_day)


def _select_states() -> Select:
    """Generate a states select that formats the states table as event rows."""
    return select(
        *EVENT_COLUMNS_FOR_STATE_SELECT,
        *STATE_COLUMNS,
        NOT_CONTEXT_ONLY,
    )


def _apply_all_hints(query: Query) -> Query:
    """Force mysql to use the right index on large selects."""
    return query.with_hint(
        States, f"FORCE INDEX ({LAST_UPDATED_INDEX})", dialect_name="mysql"
    )


def _apply_entities_hints(query: Query) -> Query:
    """Force mysql to use the right index on large selects."""
    return query.with_hint(
        States, f"FORCE INDEX ({ENTITY_ID_LAST_UPDATED_INDEX})", dialect_name="mysql"
    )


def _apply_states_filters(query: Query, start_day: dt, end_day: dt) -> Query:
    return (
        query.filter(
            (States.last_updated > start_day) & (States.last_updated < end_day)
        )
        .outerjoin(OLD_STATE, (States.old_state_id == OLD_STATE.state_id))
        .where(_missing_state_matcher())
        .where(_not_continuous_entity_matcher())
        .where(
            (States.last_updated == States.last_changed) | States.last_changed.is_(None)
        )
        .outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    )


def _missing_state_matcher() -> sqlalchemy.and_:
    # The below removes state change events that do not have
    # and old_state or the old_state is missing (newly added entities)
    # or the new_state is missing (removed entities)
    return sqlalchemy.and_(
        OLD_STATE.state_id.isnot(None),
        (States.state != OLD_STATE.state),
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


def _not_uom_attributes_matcher() -> ClauseList:
    """Prefilter ATTR_UNIT_OF_MEASUREMENT as its much faster in sql."""
    return ~StateAttributes.shared_attrs.like(
        UNIT_OF_MEASUREMENT_JSON_LIKE
    ) | ~States.attributes.like(UNIT_OF_MEASUREMENT_JSON_LIKE)


def _apply_event_entity_id_device_id_matchers(
    json_quotable_entity_ids: Iterable[str], json_quotable_device_ids: Iterable[str]
) -> sqlalchemy.or_:
    """Create matchers for the device_id and entity_id in the event_data."""
    return _apply_event_entity_id_matchers(
        json_quotable_entity_ids
    ) | _apply_event_device_id_matchers(json_quotable_device_ids)


def _apply_event_entity_id_matchers(
    json_quotable_entity_ids: Iterable[str],
) -> sqlalchemy.or_:
    """Create matchers for the entity_id in the event_data."""
    return ENTITY_ID_IN_EVENT.in_(
        json_quotable_entity_ids
    ) | OLD_ENTITY_ID_IN_EVENT.in_(json_quotable_entity_ids)


def _apply_event_device_id_matchers(
    json_quotable_device_ids: Iterable[str],
) -> ClauseList:
    """Create matchers for the device_ids in the event_data."""
    return DEVICE_ID_IN_EVENT.in_(json_quotable_device_ids)
