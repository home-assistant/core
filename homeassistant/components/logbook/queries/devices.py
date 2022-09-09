"""Devices queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

import sqlalchemy
from sqlalchemy import lambda_stmt, select
from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ClauseList
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect

from homeassistant.components.recorder.db_schema import (
    DEVICE_ID_IN_EVENT,
    EventData,
    Events,
    States,
)

from .common import (
    apply_events_context_hints,
    apply_states_context_hints,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states_context_only,
)


def _select_device_id_context_ids_sub_query(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> CompoundSelect:
    """Generate a subquery to find context ids for multiple devices."""
    inner = select_events_context_id_subquery(start_day, end_day, event_types).where(
        apply_event_device_id_matchers(json_quotable_device_ids)
    )
    return select(inner.c.context_id).group_by(inner.c.context_id)


def _apply_devices_context_union(
    query: Query,
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    json_quotable_device_ids: list[str],
) -> CompoundSelect:
    """Generate a CTE to find the device context ids and a query to find linked row."""
    devices_cte: CTE = _select_device_id_context_ids_sub_query(
        start_day,
        end_day,
        event_types,
        json_quotable_device_ids,
    ).cte()
    return query.union_all(
        apply_events_context_hints(
            select_events_context_only()
            .select_from(devices_cte)
            .outerjoin(Events, devices_cte.c.context_id == Events.context_id)
        ).outerjoin(EventData, (Events.data_id == EventData.data_id)),
        apply_states_context_hints(
            select_states_context_only()
            .select_from(devices_cte)
            .outerjoin(States, devices_cte.c.context_id == States.context_id)
        ),
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
    return DEVICE_ID_IN_EVENT.is_not(None) & sqlalchemy.cast(
        DEVICE_ID_IN_EVENT, sqlalchemy.Text()
    ).in_(json_quotable_device_ids)
