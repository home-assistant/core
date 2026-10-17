"""Action call queries for logbook."""

from sqlalchemy import lambda_stmt, select
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect, Select

from homeassistant.components.recorder.db_schema import EventData, Events, EventTypes

from .common import (
    apply_events_context_hints,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
)


def _select_action_call_context_ids_sub_query(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
) -> Select:
    """Generate a subquery to find the context ids of the action calls."""
    inner = select_events_context_id_subquery(
        start_day, end_day, event_type_ids
    ).subquery()
    return select(inner.c.context_id_bin).group_by(inner.c.context_id_bin)


def _apply_action_calls_context_union(
    sel: Select,
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
) -> CompoundSelect:
    """Generate a CTE to find the action call context ids and their linked events.

    The linked events are not limited to the time window, so the origin of a
    context, like the automation run that made the call, is found even when it
    started before the window.
    """
    action_calls_cte: CTE = _select_action_call_context_ids_sub_query(
        start_day, end_day, event_type_ids
    ).cte()
    return sel.union_all(
        apply_events_context_hints(
            select_events_context_only()
            .select_from(action_calls_cte)
            .outerjoin(
                Events, action_calls_cte.c.context_id_bin == Events.context_id_bin
            )
            .outerjoin(EventTypes, (Events.event_type_id == EventTypes.event_type_id))
            .outerjoin(EventData, (Events.data_id == EventData.data_id))
        ),
    )


def action_calls_stmt(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
) -> StatementLambdaElement:
    """Generate a logbook query for action calls."""
    return lambda_stmt(
        lambda: _apply_action_calls_context_union(
            select_events_without_states(start_day, end_day, event_type_ids),
            start_day,
            end_day,
            event_type_ids,
        ).order_by(Events.time_fired_ts)
    )
