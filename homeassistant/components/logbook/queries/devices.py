"""Devices queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

from sqlalchemy import Column, lambda_stmt, select, union_all
from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ClauseList
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.components.recorder.models import Events, States

from .common import (
    EVENT_DATA_JSON,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states_context_only,
)

DEVICE_ID_IN_EVENT: Column = EVENT_DATA_JSON["device_id"]


def _select_device_id_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple devices."""
    return select(
        union_all(
            select_events_context_id_subquery(start_day, end_day, event_types).where(
                apply_event_device_id_matchers(json_quotable_device_ids)
            ),
        ).c.context_id
    )


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
        select_events_context_only().where(Events.context_id.in_(devices_cte)),
        select_states_context_only().where(States.context_id.in_(devices_cte)),
    )


def devices_stmt(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple devices."""
    stmt = lambda_stmt(
        lambda: _apply_devices_context_union(
            select_events_without_states(start_day, end_day, event_types).where(
                apply_event_device_id_matchers(json_quotable_device_ids)
            ),
            start_day,
            end_day,
            event_types,
            json_quotable_device_ids,
        ).order_by(Events.time_fired)
    )
    return stmt


def apply_event_device_id_matchers(
    json_quotable_device_ids: Iterable[str],
) -> ClauseList:
    """Create matchers for the device_ids in the event_data."""
    return DEVICE_ID_IN_EVENT.in_(json_quotable_device_ids)
