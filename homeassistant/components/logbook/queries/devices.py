"""Devices queries for logbook."""
from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy
from sqlalchemy import lambda_stmt, select
from sqlalchemy.sql.elements import BooleanClauseList
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect, Select

from homeassistant.components import recorder

from .common import (
    apply_events_context_hints,
    apply_states_context_hints,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states_context_only,
)


def _select_device_id_context_ids_sub_query(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
    json_quotable_device_ids: list[str],
) -> Select:
    """Generate a subquery to find context ids for multiple devices."""
    inner = (
        select_events_context_id_subquery(start_day, end_day, event_type_ids)
        .where(apply_event_device_id_matchers(json_quotable_device_ids))
        .subquery()
    )
    return select(inner.c.context_id_bin).group_by(inner.c.context_id_bin)


def _apply_devices_context_union(
    sel: Select,
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
    json_quotable_device_ids: list[str],
) -> CompoundSelect:
    """Generate a CTE to find the device context ids and a query to find linked row."""
    devices_cte: CTE = _select_device_id_context_ids_sub_query(
        start_day,
        end_day,
        event_type_ids,
        json_quotable_device_ids,
    ).cte()
    return sel.union_all(
        apply_events_context_hints(
            select_events_context_only()
            .select_from(devices_cte)
            .outerjoin(
                recorder.db_schema.Events,
                devices_cte.c.context_id_bin
                == recorder.db_schema.Events.context_id_bin,
            )
            .outerjoin(
                recorder.db_schema.EventTypes,
                recorder.db_schema.Events.event_type_id
                == recorder.db_schema.EventTypes.event_type_id,
            )
            .outerjoin(
                recorder.db_schema.EventData,
                recorder.db_schema.Events.data_id
                == recorder.db_schema.EventData.data_id,
            ),
        ),
        apply_states_context_hints(
            select_states_context_only()
            .select_from(devices_cte)
            .outerjoin(
                recorder.db_schema.States,
                devices_cte.c.context_id_bin
                == recorder.db_schema.States.context_id_bin,
            )
            .outerjoin(
                recorder.db_schema.StatesMeta,
                recorder.db_schema.States.metadata_id
                == recorder.db_schema.StatesMeta.metadata_id,
            )
        ),
    )


def devices_stmt(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
    json_quotable_device_ids: list[str],
) -> StatementLambdaElement:
    """Generate a logbook query for multiple devices."""
    stmt = lambda_stmt(
        lambda: _apply_devices_context_union(
            select_events_without_states(start_day, end_day, event_type_ids).where(
                apply_event_device_id_matchers(json_quotable_device_ids)
            ),
            start_day,
            end_day,
            event_type_ids,
            json_quotable_device_ids,
        ).order_by(recorder.db_schema.Events.time_fired_ts)
    )
    return stmt


def apply_event_device_id_matchers(
    json_quotable_device_ids: Iterable[str],
) -> BooleanClauseList:
    """Create matchers for the device_ids in the event_data."""
    return recorder.db_schema.DEVICE_ID_IN_EVENT.is_not(None) & sqlalchemy.cast(
        recorder.db_schema.DEVICE_ID_IN_EVENT, sqlalchemy.Text()
    ).in_(json_quotable_device_ids)
