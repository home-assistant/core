"""Entities queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import Column, lambda_stmt, select, union_all
from sqlalchemy.orm import Query
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect

from homeassistant.components.recorder.models import (
    ENTITY_ID_LAST_UPDATED_INDEX,
    EVENT_DATA_JSON,
    OLD_FORMAT_EVENT_DATA_JSON,
    Events,
    States,
)

from .common import (
    apply_states_filters,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states,
    select_states_context_only,
)

ENTITY_ID_IN_EVENT: Column = EVENT_DATA_JSON["entity_id"]
OLD_ENTITY_ID_IN_EVENT: Column = OLD_FORMAT_EVENT_DATA_JSON["entity_id"]


def _select_entities_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> CompoundSelect:
    """Generate a subquery to find context ids for multiple entities."""
    return select(
        union_all(
            select_events_context_id_subquery(start_day, end_day, event_types).where(
                apply_event_entity_id_matchers(json_quotable_entity_ids)
            ),
            apply_entities_hints(select(States.context_id))
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id.in_(entity_ids)),
        ).c.context_id
    )


def _apply_entities_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> CompoundSelect:
    """Generate a CTE to find the entity and device context ids and a query to find linked row."""
    entities_cte: CTE = _select_entities_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quotable_entity_ids,
    ).cte()
    return query.union_all(
        states_query_for_entity_ids(start_day, end_day, entity_ids),
        select_events_context_only().where(
            Events.context_id.in_(entities_cte.select())
        ),
        select_states_context_only()
        .where(States.entity_id.not_in(entity_ids))
        .where(States.context_id.in_(entities_cte.select())),
    )


def entities_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    return lambda_stmt(
        lambda: _apply_entities_context_union(
            select_events_without_states(start_day, end_day, event_types).where(
                apply_event_entity_id_matchers(json_quotable_entity_ids)
            ),
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quotable_entity_ids,
        ).order_by(Events.time_fired)
    )


def states_query_for_entity_ids(
    start_day: dt, end_day: dt, entity_ids: list[str]
) -> Query:
    """Generate a select for states from the States table for specific entities."""
    return apply_states_filters(
        apply_entities_hints(select_states()), start_day, end_day
    ).where(States.entity_id.in_(entity_ids))


def apply_event_entity_id_matchers(
    json_quotable_entity_ids: Iterable[str],
) -> sqlalchemy.or_:
    """Create matchers for the entity_id in the event_data."""
    return ENTITY_ID_IN_EVENT.in_(
        json_quotable_entity_ids
    ) | OLD_ENTITY_ID_IN_EVENT.in_(json_quotable_entity_ids)


def apply_entities_hints(query: Query) -> Query:
    """Force mysql to use the right index on large selects."""
    return query.with_hint(
        States, f"FORCE INDEX ({ENTITY_ID_LAST_UPDATED_INDEX})", dialect_name="mysql"
    )
