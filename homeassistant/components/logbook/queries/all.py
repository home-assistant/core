"""All queries for logbook."""
from __future__ import annotations

from sqlalchemy import lambda_stmt
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.components.recorder.db_schema import (
    LAST_UPDATED_INDEX_TS,
    Events,
    States,
)
from homeassistant.components.recorder.filters import Filters

from .common import apply_states_filters, select_events_without_states, select_states


def all_stmt(
    start_day: float,
    end_day: float,
    event_type_ids: tuple[int, ...],
    filters: Filters | None,
    context_id_bin: bytes | None = None,
) -> StatementLambdaElement:
    """Generate a logbook query for all entities."""
    stmt = lambda_stmt(
        lambda: select_events_without_states(start_day, end_day, event_type_ids)
    )
    if context_id_bin is not None:
        stmt += lambda s: s.where(Events.context_id_bin == context_id_bin).union_all(
            _states_query_for_context_id(
                start_day,
                end_day,
                # https://github.com/python/mypy/issues/2608
                context_id_bin,  # type:ignore[arg-type]
            ),
        )
    elif filters and filters.has_config:
        stmt = stmt.add_criteria(
            lambda q: q.filter(filters.events_entity_filter()).union_all(  # type: ignore[union-attr]
                _states_query_for_all(start_day, end_day).where(
                    filters.states_metadata_entity_filter()  # type: ignore[union-attr]
                )
            ),
            track_on=[filters],
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
    ).with_hint(
        States, f"FORCE INDEX ({LAST_UPDATED_INDEX_TS})", dialect_name="mariadb"
    )


def _states_query_for_context_id(
    start_day: float, end_day: float, context_id_bin: bytes
) -> Select:
    return apply_states_filters(select_states(), start_day, end_day).where(
        States.context_id_bin == context_id_bin
    )
