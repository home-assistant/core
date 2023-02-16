"""All queries for logbook."""
from __future__ import annotations

from sqlalchemy import lambda_stmt
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.components.recorder.db_schema import (
    LAST_UPDATED_INDEX_TS,
    Events,
    States,
)

from .common import (
    apply_states_filters,
    legacy_select_events_context_id,
    select_events_without_states,
    select_states,
)


def all_stmt(
    start_day: float,
    end_day: float,
    event_types: tuple[str, ...],
    states_entity_filter: ColumnElement | None = None,
    events_entity_filter: ColumnElement | None = None,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate a logbook query for all entities."""
    stmt = lambda_stmt(
        lambda: select_events_without_states(start_day, end_day, event_types)
    )
    if context_id is not None:
        # Once all the old `state_changed` events
        # are gone from the database remove the
        # _legacy_select_events_context_id()
        stmt += lambda s: s.where(Events.context_id == context_id).union_all(
            _states_query_for_context_id(
                start_day,
                end_day,
                # https://github.com/python/mypy/issues/2608
                context_id,  # type:ignore[arg-type]
            ),
            legacy_select_events_context_id(
                start_day,
                end_day,
                # https://github.com/python/mypy/issues/2608
                context_id,  # type:ignore[arg-type]
            ),
        )
    else:
        if events_entity_filter is not None:
            stmt += lambda s: s.where(events_entity_filter)

        if states_entity_filter is not None:
            stmt += lambda s: s.union_all(
                _states_query_for_all(start_day, end_day).where(
                    # https://github.com/python/mypy/issues/2608
                    states_entity_filter  # type:ignore[arg-type]
                )
            )
        else:
            stmt += lambda s: s.union_all(_states_query_for_all(start_day, end_day))

    stmt += lambda s: s.order_by(Events.time_fired_ts)
    return stmt


def _states_query_for_all(start_day: float, end_day: float) -> Select:
    return apply_states_filters(_apply_all_hints(select_states()), start_day, end_day)


def _apply_all_hints(sel: Select) -> Select:
    """Force mysql to use the right index on large selects."""
    return sel.with_hint(
        States, f"FORCE INDEX ({LAST_UPDATED_INDEX_TS})", dialect_name="mysql"
    )


def _states_query_for_context_id(
    start_day: float, end_day: float, context_id: str
) -> Select:
    return apply_states_filters(select_states(), start_day, end_day).where(
        States.context_id == context_id
    )
