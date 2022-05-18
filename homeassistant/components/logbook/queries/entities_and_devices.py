"""Entities and Devices queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import lambda_stmt, select, union_all
from sqlalchemy.orm import Query
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.components.recorder.models import Events, States

from .common import (
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
    json_quotable_entity_ids: list[str],
    json_quotable_device_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple entities and multiple devices."""
    return select(
        union_all(
            select_events_context_id_subquery(start_day, end_day, event_types).where(
                _apply_event_entity_id_device_id_matchers(
                    json_quotable_entity_ids, json_quotable_device_ids
                )
            ),
            apply_entities_hints(select(States.context_id))
            .filter((States.last_updated > start_day) & (States.last_updated < end_day))
            .where(States.entity_id.in_(entity_ids)),
        ).c.context_id
    )


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
        states_query_for_entity_ids(start_day, end_day, entity_ids),
        select_events_context_only().where(Events.context_id.in_(devices_entities_cte)),
        select_states_context_only()
        .where(States.entity_id.not_in(entity_ids))
        .where(States.context_id.in_(devices_entities_cte)),
    )


def entities_devices_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str],
    json_quotable_entity_ids: list[str],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple entities."""
    stmt = lambda_stmt(
        lambda: _apply_entities_devices_context_union(
            select_events_without_states(start_day, end_day, event_types).where(
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
    )
    return stmt


def _apply_event_entity_id_device_id_matchers(
    json_quotable_entity_ids: Iterable[str], json_quotable_device_ids: Iterable[str]
) -> sqlalchemy.or_:
    """Create matchers for the device_id and entity_id in the event_data."""
    return apply_event_entity_id_matchers(
        json_quotable_entity_ids
    ) | apply_event_device_id_matchers(json_quotable_device_ids)
