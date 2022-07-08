"""Entities queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import lambda_stmt, select, union_all
from sqlalchemy.orm import Query
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect

from homeassistant.components.recorder.db_schema import (
    ENTITY_ID_IN_EVENT,
    ENTITY_ID_LAST_UPDATED_INDEX,
    OLD_ENTITY_ID_IN_EVENT,
    EventData,
    Events,
    States,
)

from .common import (
    apply_events_context_hints,
    apply_states_context_hints,
    apply_states_filters,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states,
    select_states_context_only,
)


def _select_entities_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
) -> CompoundSelect:
    """Generate a subquery to find context ids for multiple entities."""
    union = union_all(
        select_events_context_id_subquery(start_day, end_day, event_types).where(
            apply_event_entity_id_matchers(json_quoted_entity_ids)
        ),
        apply_entities_hints(select(States.context_id))
        .filter((States.last_updated > start_day) & (States.last_updated < end_day))
        .where(States.entity_id.in_(entity_ids)),
    )
    return select(union.c.context_id).group_by(union.c.context_id)


def _apply_entities_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
) -> CompoundSelect:
    """Generate a CTE to find the entity and device context ids and a query to find linked row."""
    entities_cte: CTE = _select_entities_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quoted_entity_ids,
    ).cte()
    # We used to optimize this to exclude rows we already in the union with
    # a States.entity_id.not_in(entity_ids) but that made the
    # query much slower on MySQL, and since we already filter them away
    # in the python code anyways since they will have context_only
    # set on them the impact is minimal.
    return query.union_all(
        states_query_for_entity_ids(start_day, end_day, entity_ids),
        apply_events_context_hints(
            select_events_context_only()
            .select_from(entities_cte)
            .outerjoin(Events, entities_cte.c.context_id == Events.context_id)
        ).outerjoin(EventData, (Events.data_id == EventData.data_id)),
        apply_states_context_hints(
            select_states_context_only()
            .select_from(entities_cte)
            .outerjoin(States, entities_cte.c.context_id == States.context_id)
        ),
    )


def entities_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    return lambda_stmt(
        lambda: _apply_entities_context_union(
            select_events_without_states(start_day, end_day, event_types).where(
                apply_event_entity_id_matchers(json_quoted_entity_ids)
            ),
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quoted_entity_ids,
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
    json_quoted_entity_ids: Iterable[str],
) -> sqlalchemy.or_:
    """Create matchers for the entity_id in the event_data."""
    return sqlalchemy.or_(
        ENTITY_ID_IN_EVENT.is_not(None)
        & sqlalchemy.cast(ENTITY_ID_IN_EVENT, sqlalchemy.Text()).in_(
            json_quoted_entity_ids
        ),
        OLD_ENTITY_ID_IN_EVENT.is_not(None)
        & sqlalchemy.cast(OLD_ENTITY_ID_IN_EVENT, sqlalchemy.Text()).in_(
            json_quoted_entity_ids
        ),
    )


def apply_entities_hints(query: Query) -> Query:
    """Force mysql to use the right index on large selects."""
    return query.with_hint(
        States, f"FORCE INDEX ({ENTITY_ID_LAST_UPDATED_INDEX})", dialect_name="mysql"
    )
