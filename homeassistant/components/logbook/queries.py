"""Queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import JSON, lambda_stmt, select, type_coerce, union_all
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
    LAST_UPDATED_INDEX,
    EventData,
    Events,
    StateAttributes,
    States,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

ENTITY_ID_JSON_TEMPLATE = '%"entity_id":"{}"%'

CONTINUOUS_DOMAINS = {PROXIMITY_DOMAIN, SENSOR_DOMAIN}
CONTINUOUS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in CONTINUOUS_DOMAINS]

UNIT_OF_MEASUREMENT_JSON = '"unit_of_measurement":'
UNIT_OF_MEASUREMENT_JSON_LIKE = f"%{UNIT_OF_MEASUREMENT_JSON}%"

OLD_STATE = aliased(States, name="old_state")


SHARED_ATTRS_JSON = type_coerce(
    StateAttributes.shared_attrs.cast(JSON_VARIENT_CAST), JSON(none_as_null=True)
)
OLD_FORMAT_ATTRS_JSON = type_coerce(
    States.attributes.cast(JSON_VARIENT_CAST), JSON(none_as_null=True)
)


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
    filters: Filters | None = None,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate the logbook statement for a logbook request."""

    # No entities: logbook sends everything for the timeframe
    # limited by the context_id and the yaml configured filter
    if not entity_ids:
        entity_filter = filters.entity_filter() if filters else None
        return _all_stmt(start_day, end_day, event_types, entity_filter, context_id)

    # Multiple entities: logbook sends everything for the timeframe for the entities
    #
    # This is the least efficient query because we use
    # like matching which means part of the query has to be built each
    # time when the entity_ids are not in the cache
    if len(entity_ids) > 1:
        return _entities_stmt(start_day, end_day, event_types, entity_ids)

    # Single entity: logbook sends everything for the timeframe for the entity
    entity_id = entity_ids[0]
    entity_like = ENTITY_ID_JSON_TEMPLATE.format(entity_id)
    return _single_entity_stmt(start_day, end_day, event_types, entity_id, entity_like)


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
) -> Select:
    """Generate a subquery to find context ids for multiple entities."""
    return select(
        union_all(
            _select_events_context_id_subquery(start_day, end_day, event_types).where(
                _apply_event_entity_id_matchers(entity_ids)
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


def _entities_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
    )
    stmt = stmt.add_criteria(
        lambda s: s.where(_apply_event_entity_id_matchers(entity_ids)).union_all(
            _states_query_for_entity_ids(start_day, end_day, entity_ids),
            _select_events_context_only().where(
                Events.context_id.in_(
                    _select_entities_context_ids_sub_query(
                        start_day,
                        end_day,
                        event_types,
                        entity_ids,
                    )
                )
            ),
        ),
        # Since _apply_event_entity_id_matchers generates multiple
        # like statements we need to use the entity_ids in the
        # the cache key since the sql can change based on the
        # likes.
        track_on=(str(entity_ids),),
    )
    stmt += lambda s: s.order_by(Events.time_fired)
    return stmt


def _select_entity_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_id: str,
    entity_id_like: str,
) -> Select:
    """Generate a subquery to find context ids for a single entity."""
    return select(
        union_all(
            _select_events_context_id_subquery(start_day, end_day, event_types).where(
                Events.event_data.like(entity_id_like)
                | EventData.shared_data.like(entity_id_like)
            ),
            _apply_entities_hints(select(States.context_id))
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id == entity_id),
        ).c.context_id
    )


def _single_entity_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_id: str,
    entity_id_like: str,
) -> StatementLambdaElement:
    """Generate a logbook query for a single entity."""
    stmt = lambda_stmt(
        lambda: _select_events_without_states(start_day, end_day, event_types)
        .where(
            Events.event_data.like(entity_id_like)
            | EventData.shared_data.like(entity_id_like)
        )
        .union_all(
            _states_query_for_entity_id(start_day, end_day, entity_id),
            _select_events_context_only().where(
                Events.context_id.in_(
                    _select_entity_context_ids_sub_query(
                        start_day, end_day, event_types, entity_id, entity_id_like
                    )
                )
            ),
        )
        .order_by(Events.time_fired)
    )
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


def _states_query_for_entity_id(start_day: dt, end_day: dt, entity_id: str) -> Query:
    return _apply_states_filters(
        _apply_entities_hints(_select_states()), start_day, end_day
    ).where(States.entity_id == entity_id)


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


def _apply_event_entity_id_matchers(entity_ids: Iterable[str]) -> sqlalchemy.or_:
    """Create matchers for the entity_id in the event_data."""
    ors = []
    for entity_id in entity_ids:
        like = ENTITY_ID_JSON_TEMPLATE.format(entity_id)
        ors.append(Events.event_data.like(like))
        ors.append(EventData.shared_data.like(like))
    return sqlalchemy.or_(*ors)
