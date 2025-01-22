"""Provide pre-made queries on top of the recorder component."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from itertools import groupby
from operator import attrgetter
import time
from typing import Any, cast

from sqlalchemy import Column, Text, and_, func, lambda_stmt, or_, select
from sqlalchemy.engine.row import Row
from sqlalchemy.orm.properties import MappedColumn
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.const import COMPRESSED_STATE_LAST_UPDATED, COMPRESSED_STATE_STATE
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.helpers.recorder import get_instance
import homeassistant.util.dt as dt_util

from ..db_schema import StateAttributes, States
from ..filters import Filters
from ..models import process_timestamp_to_utc_isoformat
from ..models.legacy import LegacyLazyState, legacy_row_to_compressed_state
from ..util import execute_stmt_lambda_element, session_scope
from .const import (
    LAST_CHANGED_KEY,
    NEED_ATTRIBUTE_DOMAINS,
    SIGNIFICANT_DOMAINS,
    SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE,
    STATE_KEY,
)

_BASE_STATES = (
    States.entity_id,
    States.state,
    States.last_changed_ts,
    States.last_updated_ts,
)
_BASE_STATES_NO_LAST_CHANGED = (
    States.entity_id,
    States.state,
    literal(value=None).label("last_changed_ts"),
    States.last_updated_ts,
)
_QUERY_STATE_NO_ATTR = (
    *_BASE_STATES,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
)
_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED = (
    *_BASE_STATES_NO_LAST_CHANGED,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
)
_BASE_STATES_PRE_SCHEMA_31 = (
    States.entity_id,
    States.state,
    States.last_changed,
    States.last_updated,
)
_BASE_STATES_NO_LAST_CHANGED_PRE_SCHEMA_31 = (
    States.entity_id,
    States.state,
    literal(value=None, type_=Text).label("last_changed"),
    States.last_updated,
)
_QUERY_STATE_NO_ATTR_PRE_SCHEMA_31 = (
    *_BASE_STATES_PRE_SCHEMA_31,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
)
_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED_PRE_SCHEMA_31 = (
    *_BASE_STATES_NO_LAST_CHANGED_PRE_SCHEMA_31,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
)
# Remove QUERY_STATES_PRE_SCHEMA_25
# and the migration_in_progress check
# once schema 26 is created
_QUERY_STATES_PRE_SCHEMA_25 = (
    *_BASE_STATES_PRE_SCHEMA_31,
    States.attributes,
    literal(value=None, type_=Text).label("shared_attrs"),
)
_QUERY_STATES_PRE_SCHEMA_25_NO_LAST_CHANGED = (
    *_BASE_STATES_NO_LAST_CHANGED_PRE_SCHEMA_31,
    States.attributes,
    literal(value=None, type_=Text).label("shared_attrs"),
)
_QUERY_STATES_PRE_SCHEMA_31 = (
    *_BASE_STATES_PRE_SCHEMA_31,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_QUERY_STATES_NO_LAST_CHANGED_PRE_SCHEMA_31 = (
    *_BASE_STATES_NO_LAST_CHANGED_PRE_SCHEMA_31,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_QUERY_STATES = (
    *_BASE_STATES,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_QUERY_STATES_NO_LAST_CHANGED = (
    *_BASE_STATES_NO_LAST_CHANGED,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_FIELD_MAP = {
    cast(MappedColumn, field).name: idx
    for idx, field in enumerate(_QUERY_STATE_NO_ATTR)
}
_FIELD_MAP_PRE_SCHEMA_31 = {
    cast(MappedColumn, field).name: idx
    for idx, field in enumerate(_QUERY_STATES_PRE_SCHEMA_31)
}


def _lambda_stmt_and_join_attributes(
    no_attributes: bool, include_last_changed: bool = True
) -> tuple[StatementLambdaElement, bool]:
    """Return the lambda_stmt and if StateAttributes should be joined.

    Because these are lambda_stmt the values inside the lambdas need
    to be explicitly written out to avoid caching the wrong values.
    """
    # If no_attributes was requested we do the query
    # without the attributes fields and do not join the
    # state_attributes table
    if no_attributes:
        if include_last_changed:
            return (
                lambda_stmt(lambda: select(*_QUERY_STATE_NO_ATTR)),
                False,
            )
        return (
            lambda_stmt(lambda: select(*_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED)),
            False,
        )

    if include_last_changed:
        return lambda_stmt(lambda: select(*_QUERY_STATES)), True
    return lambda_stmt(lambda: select(*_QUERY_STATES_NO_LAST_CHANGED)), True


def get_significant_states(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> dict[str, list[State | dict[str, Any]]]:
    """Wrap get_significant_states_with_session with an sql session."""
    with session_scope(hass=hass, read_only=True) as session:
        return get_significant_states_with_session(
            hass,
            session,
            start_time,
            end_time,
            entity_ids,
            filters,
            include_start_time_state,
            significant_changes_only,
            minimal_response,
            no_attributes,
            compressed_state_format,
        )


def _significant_states_stmt(
    start_time: datetime,
    end_time: datetime | None,
    entity_ids: list[str],
    significant_changes_only: bool,
    no_attributes: bool,
) -> StatementLambdaElement:
    """Query the database for significant state changes."""
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=not significant_changes_only
    )
    if (
        len(entity_ids) == 1
        and significant_changes_only
        and split_entity_id(entity_ids[0])[0] not in SIGNIFICANT_DOMAINS
    ):
        stmt += lambda q: q.filter(
            (States.last_changed_ts == States.last_updated_ts)
            | States.last_changed_ts.is_(None)
        )
    elif significant_changes_only:
        stmt += lambda q: q.filter(
            or_(
                *[
                    States.entity_id.like(entity_domain)
                    for entity_domain in SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE
                ],
                (
                    (States.last_changed_ts == States.last_updated_ts)
                    | States.last_changed_ts.is_(None)
                ),
            )
        )
    stmt += lambda q: q.filter(States.entity_id.in_(entity_ids))

    start_time_ts = start_time.timestamp()
    stmt += lambda q: q.filter(States.last_updated_ts > start_time_ts)
    if end_time:
        end_time_ts = end_time.timestamp()
        stmt += lambda q: q.filter(States.last_updated_ts < end_time_ts)

    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    stmt += lambda q: q.order_by(States.entity_id, States.last_updated_ts)
    return stmt


def get_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> dict[str, list[State | dict[str, Any]]]:
    """Return states changes during UTC period start_time - end_time.

    entity_ids is an optional iterable of entities to include in the results.

    filters is an optional SQLAlchemy filter which will be applied to the database
    queries unless entity_ids is given, in which case its ignored.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    if filters is not None:
        raise NotImplementedError("Filters are no longer supported")
    if not entity_ids:
        raise ValueError("entity_ids must be provided")
    stmt = _significant_states_stmt(
        start_time,
        end_time,
        entity_ids,
        significant_changes_only,
        no_attributes,
    )
    states = execute_stmt_lambda_element(session, stmt, None, end_time)
    return _sorted_states_to_dict(
        hass,
        session,
        states,
        start_time,
        entity_ids,
        include_start_time_state,
        minimal_response,
        no_attributes,
        compressed_state_format,
    )


def get_full_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    no_attributes: bool = False,
) -> dict[str, list[State]]:
    """Variant of get_significant_states_with_session.

    Difference with get_significant_states_with_session is that it does not
    return minimal responses.
    """
    return cast(
        dict[str, list[State]],
        get_significant_states_with_session(
            hass=hass,
            session=session,
            start_time=start_time,
            end_time=end_time,
            entity_ids=entity_ids,
            filters=filters,
            include_start_time_state=include_start_time_state,
            significant_changes_only=significant_changes_only,
            minimal_response=False,
            no_attributes=no_attributes,
        ),
    )


def _state_changed_during_period_stmt(
    start_time: datetime,
    end_time: datetime | None,
    entity_id: str,
    no_attributes: bool,
    descending: bool,
    limit: int | None,
) -> StatementLambdaElement:
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=False
    )
    start_time_ts = start_time.timestamp()
    stmt += lambda q: q.filter(
        (
            (States.last_changed_ts == States.last_updated_ts)
            | States.last_changed_ts.is_(None)
        )
        & (States.last_updated_ts > start_time_ts)
    )
    if end_time:
        end_time_ts = end_time.timestamp()
        stmt += lambda q: q.filter(States.last_updated_ts < end_time_ts)
    stmt += lambda q: q.filter(States.entity_id == entity_id)
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    if descending:
        stmt += lambda q: q.order_by(States.entity_id, States.last_updated_ts.desc())
    else:
        stmt += lambda q: q.order_by(States.entity_id, States.last_updated_ts)

    if limit:
        stmt += lambda q: q.limit(limit)
    return stmt


def state_changes_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_id: str | None = None,
    no_attributes: bool = False,
    descending: bool = False,
    limit: int | None = None,
    include_start_time_state: bool = True,
) -> dict[str, list[State]]:
    """Return states changes during UTC period start_time - end_time."""
    if not entity_id:
        raise ValueError("entity_id must be provided")
    entity_ids = [entity_id.lower()]
    with session_scope(hass=hass, read_only=True) as session:
        stmt = _state_changed_during_period_stmt(
            start_time,
            end_time,
            entity_id,
            no_attributes,
            descending,
            limit,
        )
        states = execute_stmt_lambda_element(session, stmt, None, end_time)
        return cast(
            dict[str, list[State]],
            _sorted_states_to_dict(
                hass,
                session,
                states,
                start_time,
                entity_ids,
                include_start_time_state=include_start_time_state,
            ),
        )


def _get_last_state_changes_stmt(
    number_of_states: int, entity_id: str
) -> StatementLambdaElement:
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        False, include_last_changed=False
    )
    stmt += lambda q: q.where(
        States.state_id
        == (
            select(States.state_id)
            .filter(States.entity_id == entity_id)
            .order_by(States.last_updated_ts.desc())
            .limit(number_of_states)
            .subquery()
        ).c.state_id
    )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )

    stmt += lambda q: q.order_by(States.state_id.desc())
    return stmt


def get_last_state_changes(
    hass: HomeAssistant, number_of_states: int, entity_id: str
) -> dict[str, list[State]]:
    """Return the last number_of_states."""
    entity_id_lower = entity_id.lower()
    entity_ids = [entity_id_lower]

    with session_scope(hass=hass, read_only=True) as session:
        stmt = _get_last_state_changes_stmt(number_of_states, entity_id_lower)
        states = list(execute_stmt_lambda_element(session, stmt))
        return cast(
            dict[str, list[State]],
            _sorted_states_to_dict(
                hass,
                session,
                reversed(states),
                dt_util.utcnow(),
                entity_ids,
                include_start_time_state=False,
            ),
        )


def _get_states_for_entities_stmt(
    run_start_ts: float,
    utc_point_in_time: datetime,
    entity_ids: list[str],
    no_attributes: bool,
) -> StatementLambdaElement:
    """Baked query to get states for specific entities."""
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=True
    )
    # We got an include-list of entities, accelerate the query by filtering already
    # in the inner query.
    utc_point_in_time_ts = utc_point_in_time.timestamp()
    stmt += lambda q: q.join(
        (
            most_recent_states_for_entities_by_date := (
                select(
                    States.entity_id.label("max_entity_id"),
                    func.max(States.last_updated_ts).label("max_last_updated"),
                )
                .filter(
                    (States.last_updated_ts >= run_start_ts)
                    & (States.last_updated_ts < utc_point_in_time_ts)
                )
                .filter(States.entity_id.in_(entity_ids))
                .group_by(States.entity_id)
                .subquery()
            )
        ),
        and_(
            States.entity_id == most_recent_states_for_entities_by_date.c.max_entity_id,
            States.last_updated_ts
            == most_recent_states_for_entities_by_date.c.max_last_updated,
        ),
    )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    return stmt


def _get_rows_with_session(
    hass: HomeAssistant,
    session: Session,
    utc_point_in_time: datetime,
    entity_ids: list[str],
    *,
    no_attributes: bool = False,
) -> Iterable[Row]:
    """Return the states at a specific point in time."""
    if len(entity_ids) == 1:
        return execute_stmt_lambda_element(
            session,
            _get_single_entity_states_stmt(
                utc_point_in_time, entity_ids[0], no_attributes
            ),
        )

    oldest_ts = get_instance(hass).states_manager.oldest_ts

    if oldest_ts is None or oldest_ts > utc_point_in_time.timestamp():
        # We don't have any states for the requested time
        return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    stmt = _get_states_for_entities_stmt(
        oldest_ts, utc_point_in_time, entity_ids, no_attributes
    )
    return execute_stmt_lambda_element(session, stmt)


def _get_single_entity_states_stmt(
    utc_point_in_time: datetime,
    entity_id: str,
    no_attributes: bool = False,
) -> StatementLambdaElement:
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=True
    )
    utc_point_in_time_ts = utc_point_in_time.timestamp()
    stmt += (
        lambda q: q.filter(
            States.last_updated_ts < utc_point_in_time_ts,
            States.entity_id == entity_id,
        )
        .order_by(States.last_updated_ts.desc())
        .limit(1)
    )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    return stmt


def _sorted_states_to_dict(
    hass: HomeAssistant,
    session: Session,
    states: Iterable[Row],
    start_time: datetime,
    entity_ids: list[str],
    include_start_time_state: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> dict[str, list[State | dict[str, Any]]]:
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    States must be sorted by entity_id and last_updated

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    state_class: Callable[
        [Row, dict[str, dict[str, Any]], datetime | None], State | dict[str, Any]
    ]
    if compressed_state_format:
        state_class = legacy_row_to_compressed_state
        attr_time = COMPRESSED_STATE_LAST_UPDATED
        attr_state = COMPRESSED_STATE_STATE
    else:
        state_class = LegacyLazyState
        attr_time = LAST_CHANGED_KEY
        attr_state = STATE_KEY

    result: dict[str, list[State | dict[str, Any]]] = defaultdict(list)
    # Set all entity IDs to empty lists in result set to maintain the order
    for ent_id in entity_ids:
        result[ent_id] = []

    # Get the states at the start time
    time.perf_counter()
    initial_states: dict[str, Row] = {}
    if include_start_time_state:
        initial_states = {
            row.entity_id: row
            for row in _get_rows_with_session(
                hass,
                session,
                start_time,
                entity_ids,
                no_attributes=no_attributes,
            )
        }

    if len(entity_ids) == 1:
        states_iter: Iterable[tuple[str, Iterator[Row]]] = (
            (entity_ids[0], iter(states)),
        )
    else:
        key_func = attrgetter("entity_id")
        states_iter = groupby(states, key_func)

    # Append all changes to it
    for ent_id, group in states_iter:
        attr_cache: dict[str, dict[str, Any]] = {}
        prev_state: Column | str
        ent_results = result[ent_id]
        if row := initial_states.pop(ent_id, None):
            prev_state = row.state
            ent_results.append(state_class(row, attr_cache, start_time))

        if not minimal_response or split_entity_id(ent_id)[0] in NEED_ATTRIBUTE_DOMAINS:
            ent_results.extend(
                state_class(db_state, attr_cache, None) for db_state in group
            )
            continue

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            if (first_state := next(group, None)) is None:
                continue
            prev_state = first_state.state
            ent_results.append(state_class(first_state, attr_cache, None))

        state_idx = _FIELD_MAP["state"]

        #
        # minimal_response only makes sense with last_updated == last_updated
        #
        # We use last_updated for for last_changed since its the same
        #
        # With minimal response we do not care about attribute
        # changes so we can filter out duplicate states
        last_updated_ts_idx = _FIELD_MAP["last_updated_ts"]
        if compressed_state_format:
            for row in group:
                if (state := row[state_idx]) != prev_state:
                    ent_results.append(
                        {
                            attr_state: state,
                            attr_time: row[last_updated_ts_idx],
                        }
                    )
                    prev_state = state
            continue

        for row in group:
            if (state := row[state_idx]) != prev_state:
                ent_results.append(
                    {
                        attr_state: state,
                        attr_time: process_timestamp_to_utc_isoformat(
                            dt_util.utc_from_timestamp(row[last_updated_ts_idx])
                        ),
                    }
                )
                prev_state = state

    # If there are no states beyond the initial state,
    # the state a was never popped from initial_states
    for ent_id, row in initial_states.items():
        result[ent_id].append(state_class(row, {}, start_time))

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}
