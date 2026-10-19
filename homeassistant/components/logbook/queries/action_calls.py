"""Action call queries for logbook."""

from sqlalchemy import lambda_stmt, select, union_all
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import CTE, CompoundSelect, Select

from homeassistant.components.recorder.db_schema import (
    EventData,
    Events,
    EventTypes,
    States,
    StatesMeta,
)

from .common import (
    apply_events_context_hints,
    apply_states_context_hints,
    select_events_context_id_subquery,
    select_events_context_only,
    select_events_without_states,
    select_states_context_only,
)


def _select_action_call_context_ids_sub_query(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
) -> Select:
    """Generate a subquery to find the context ids of the action calls and parents."""
    union = union_all(
        select_events_context_id_subquery(start_day, end_day, event_type_ids),
        select(Events.context_parent_id_bin.label("context_id_bin"))
        .where((Events.time_fired_ts > start_day) & (Events.time_fired_ts < end_day))
        .where(Events.event_type_id.in_(event_type_ids))
        .where(Events.context_parent_id_bin.is_not(None)),
    ).subquery()
    return select(union.c.context_id_bin).group_by(union.c.context_id_bin)


def _apply_action_calls_context_union(
    sel: Select,
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
) -> CompoundSelect:
    """Generate a CTE to find the action call context ids and their linked rows.

    The linked events and states are not limited to the time window, so the
    origin of a context or its parent, like the automation run, action, or
    state change that made the call, is found even when it was before the
    window.
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
        apply_states_context_hints(
            select_states_context_only()
            .select_from(action_calls_cte)
            .outerjoin(
                States, action_calls_cte.c.context_id_bin == States.context_id_bin
            )
            .outerjoin(StatesMeta, (States.metadata_id == StatesMeta.metadata_id))
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
