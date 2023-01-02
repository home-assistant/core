"""Entities and Devices queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import lambda_stmt, select, union_all
from sqlalchemy.orm import Query
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect

from homeassistant.components.recorder.db_schema import EventData, Events, States

from .common import (
    apply_events_context_hints,
    apply_states_context_hints,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states_context_only,
)
from .devices import apply_event_device_id_matchers
from .entities import (
    apply_entities_hints,
    apply_event_entity_id_matchers,
    states_query_for_entity_ids,
)


def _select_entities_device_id_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
    json_quoted_device_ids: list[str],
) -> CompoundSelect:
    """Generate a subquery to find context ids for multiple entities and multiple devices."""
    union = union_all(
        select_events_context_id_subquery(start_day, end_day, event_types).where(
            _apply_event_entity_id_device_id_matchers(
                json_quoted_entity_ids, json_quoted_device_ids
            )
        ),
        apply_entities_hints(select(States.context_id))
        .filter((States.last_updated > start_day) & (States.last_updated < end_day))
        .where(States.entity_id.in_(entity_ids)),
    )
    return select(union.c.context_id).group_by(union.c.context_id)


def _apply_entities_devices_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
    json_quoted_device_ids: list[str],
) -> CompoundSelect:
    devices_entities_cte: CTE = _select_entities_device_id_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        entity_ids,
        json_quoted_entity_ids,
        json_quoted_device_ids,
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
            .select_from(devices_entities_cte)
            .outerjoin(Events, devices_entities_cte.c.context_id == Events.context_id)
        ).outerjoin(EventData, (Events.data_id == EventData.data_id)),
        apply_states_context_hints(
            select_states_context_only()
            .select_from(devices_entities_cte)
            .outerjoin(States, devices_entities_cte.c.context_id == States.context_id)
        ),
    )


def entities_devices_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quoted_entity_ids: list[str],
    json_quoted_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _apply_entities_devices_context_union(
            select_events_without_states(start_day, end_day, event_types).where(
                _apply_event_entity_id_device_id_matchers(
                    json_quoted_entity_ids, json_quoted_device_ids
                )
            ),
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quoted_entity_ids,
            json_quoted_device_ids,
        ).order_by(Events.time_fired)
    )
    return stmt


def _apply_event_entity_id_device_id_matchers(
    json_quoted_entity_ids: Iterable[str], json_quoted_device_ids: Iterable[str]
) -> sqlalchemy.or_:
    """Create matchers for the device_id and entity_id in the event_data."""
    return apply_event_entity_id_matchers(
        json_quoted_entity_ids
    ) | apply_event_device_id_matchers(json_quoted_device_ids)
