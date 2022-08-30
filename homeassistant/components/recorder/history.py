"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, MutableMapping
from datetime import datetime
from itertools import groupby
import logging
import time
from typing import Any, cast

from sqlalchemy import Column, Text, and_, func, lambda_stmt, or_, select
from sqlalchemy.engine.row import Row
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Subquery

from homeassistant.components.websocket_api.const import (
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
import homeassistant.util.dt as dt_util

from .. import recorder
from .db_schema import RecorderRuns, StateAttributes, States
from .filters import Filters
from .models import (
    LazyState,
    process_datetime_to_timestamp,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
    row_to_compressed_state,
)
from .util import execute_stmt_lambda_element, session_scope

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

STATE_KEY = "state"
LAST_CHANGED_KEY = "last_changed"

SIGNIFICANT_DOMAINS = {
    "climate",
    "device_tracker",
    "humidifier",
    "thermostat",
    "water_heater",
}
SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in SIGNIFICANT_DOMAINS]
IGNORE_DOMAINS = {"zone", "scene"}
IGNORE_DOMAINS_ENTITY_ID_LIKE = [f"{domain}.%" for domain in IGNORE_DOMAINS]
NEED_ATTRIBUTE_DOMAINS = {
    "climate",
    "humidifier",
    "input_datetime",
    "thermostat",
    "water_heater",
}

BASE_STATES = [
    States.entity_id,
    States.state,
    States.last_changed,
    States.last_updated,
]
BASE_STATES_NO_LAST_CHANGED = [
    States.entity_id,
    States.state,
    literal(value=None, type_=Text).label("last_changed"),
    States.last_updated,
]
QUERY_STATE_NO_ATTR = [
    *BASE_STATES,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATE_NO_ATTR_NO_LAST_CHANGED = [
    *BASE_STATES_NO_LAST_CHANGED,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
]
# Remove QUERY_STATES_PRE_SCHEMA_25
# and the migration_in_progress check
# once schema 26 is created
QUERY_STATES_PRE_SCHEMA_25 = [
    *BASE_STATES,
    States.attributes,
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATES_PRE_SCHEMA_25_NO_LAST_CHANGED = [
    *BASE_STATES_NO_LAST_CHANGED,
    States.attributes,
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATES = [
    *BASE_STATES,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
]
QUERY_STATES_NO_LAST_CHANGED = [
    *BASE_STATES_NO_LAST_CHANGED,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
]


def _schema_version(hass: HomeAssistant) -> int:
    return recorder.get_instance(hass).schema_version


def lambda_stmt_and_join_attributes(
    schema_version: int, no_attributes: bool, include_last_changed: bool = True
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
            return lambda_stmt(lambda: select(*QUERY_STATE_NO_ATTR)), False
        return (
            lambda_stmt(lambda: select(*QUERY_STATE_NO_ATTR_NO_LAST_CHANGED)),
            False,
        )
    # If we in the process of migrating schema we do
    # not want to join the state_attributes table as we
    # do not know if it will be there yet
    if schema_version < 25:
        if include_last_changed:
            return (
                lambda_stmt(lambda: select(*QUERY_STATES_PRE_SCHEMA_25)),
                False,
            )
        return (
            lambda_stmt(lambda: select(*QUERY_STATES_PRE_SCHEMA_25_NO_LAST_CHANGED)),
            False,
        )
    # Finally if no migration is in progress and no_attributes
    # was not requested, we query both attributes columns and
    # join state_attributes
    if include_last_changed:
        return lambda_stmt(lambda: select(*QUERY_STATES)), True
    return lambda_stmt(lambda: select(*QUERY_STATES_NO_LAST_CHANGED)), True


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
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Wrap get_significant_states_with_session with an sql session."""
    with session_scope(hass=hass) as session:
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


def _ignore_domains_filter(query: Query) -> Query:
    """Add a filter to ignore domains we do not fetch history for."""
    return query.filter(
        and_(
            *[
                ~States.entity_id.like(entity_domain)
                for entity_domain in IGNORE_DOMAINS_ENTITY_ID_LIKE
            ]
        )
    )


def _significant_states_stmt(
    schema_version: int,
    start_time: datetime,
    end_time: datetime | None,
    entity_ids: list[str] | None,
    filters: Filters | None,
    significant_changes_only: bool,
    no_attributes: bool,
) -> StatementLambdaElement:
    """Query the database for significant state changes."""
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, no_attributes, include_last_changed=not significant_changes_only
    )
    if (
        entity_ids
        and len(entity_ids) == 1
        and significant_changes_only
        and split_entity_id(entity_ids[0])[0] not in SIGNIFICANT_DOMAINS
    ):
        stmt += lambda q: q.filter(
            (States.last_changed == States.last_updated) | States.last_changed.is_(None)
        )
    elif significant_changes_only:
        stmt += lambda q: q.filter(
            or_(
                *[
                    States.entity_id.like(entity_domain)
                    for entity_domain in SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE
                ],
                (
                    (States.last_changed == States.last_updated)
                    | States.last_changed.is_(None)
                ),
            )
        )

    if entity_ids:
        stmt += lambda q: q.filter(States.entity_id.in_(entity_ids))
    else:
        stmt += _ignore_domains_filter
        if filters and filters.has_config:
            entity_filter = filters.states_entity_filter()
            stmt = stmt.add_criteria(
                lambda q: q.filter(entity_filter), track_on=[filters]
            )

    stmt += lambda q: q.filter(States.last_updated > start_time)
    if end_time:
        stmt += lambda q: q.filter(States.last_updated < end_time)

    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    stmt += lambda q: q.order_by(States.entity_id, States.last_updated)
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
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """
    Return states changes during UTC period start_time - end_time.

    entity_ids is an optional iterable of entities to include in the results.

    filters is an optional SQLAlchemy filter which will be applied to the database
    queries unless entity_ids is given, in which case its ignored.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    stmt = _significant_states_stmt(
        _schema_version(hass),
        start_time,
        end_time,
        entity_ids,
        filters,
        significant_changes_only,
        no_attributes,
    )
    states = execute_stmt_lambda_element(
        session, stmt, None if entity_ids else start_time, end_time
    )
    return _sorted_states_to_dict(
        hass,
        session,
        states,
        start_time,
        entity_ids,
        filters,
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
) -> MutableMapping[str, list[State]]:
    """Variant of get_significant_states_with_session that does not return minimal responses."""
    return cast(
        MutableMapping[str, list[State]],
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
    schema_version: int,
    start_time: datetime,
    end_time: datetime | None,
    entity_id: str | None,
    no_attributes: bool,
    descending: bool,
    limit: int | None,
) -> StatementLambdaElement:
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, no_attributes, include_last_changed=False
    )
    stmt += lambda q: q.filter(
        ((States.last_changed == States.last_updated) | States.last_changed.is_(None))
        & (States.last_updated > start_time)
    )
    if end_time:
        stmt += lambda q: q.filter(States.last_updated < end_time)
    if entity_id:
        stmt += lambda q: q.filter(States.entity_id == entity_id)
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    if descending:
        stmt += lambda q: q.order_by(States.entity_id, States.last_updated.desc())
    else:
        stmt += lambda q: q.order_by(States.entity_id, States.last_updated)
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
) -> MutableMapping[str, list[State]]:
    """Return states changes during UTC period start_time - end_time."""
    entity_id = entity_id.lower() if entity_id is not None else None
    entity_ids = [entity_id] if entity_id is not None else None

    with session_scope(hass=hass) as session:
        stmt = _state_changed_during_period_stmt(
            _schema_version(hass),
            start_time,
            end_time,
            entity_id,
            no_attributes,
            descending,
            limit,
        )
        states = execute_stmt_lambda_element(
            session, stmt, None if entity_id else start_time, end_time
        )
        return cast(
            MutableMapping[str, list[State]],
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
    schema_version: int, number_of_states: int, entity_id: str | None
) -> StatementLambdaElement:
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, False, include_last_changed=False
    )
    stmt += lambda q: q.filter(
        (States.last_changed == States.last_updated) | States.last_changed.is_(None)
    )
    if entity_id:
        stmt += lambda q: q.filter(States.entity_id == entity_id)
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    stmt += lambda q: q.order_by(States.entity_id, States.last_updated.desc()).limit(
        number_of_states
    )
    return stmt


def get_last_state_changes(
    hass: HomeAssistant, number_of_states: int, entity_id: str | None
) -> MutableMapping[str, list[State]]:
    """Return the last number_of_states."""
    start_time = dt_util.utcnow()
    entity_id = entity_id.lower() if entity_id is not None else None
    entity_ids = [entity_id] if entity_id is not None else None

    with session_scope(hass=hass) as session:
        stmt = _get_last_state_changes_stmt(
            _schema_version(hass), number_of_states, entity_id
        )
        states = list(execute_stmt_lambda_element(session, stmt))
        return cast(
            MutableMapping[str, list[State]],
            _sorted_states_to_dict(
                hass,
                session,
                reversed(states),
                start_time,
                entity_ids,
                include_start_time_state=False,
            ),
        )


def _get_states_for_entites_stmt(
    schema_version: int,
    run_start: datetime,
    utc_point_in_time: datetime,
    entity_ids: list[str],
    no_attributes: bool,
) -> StatementLambdaElement:
    """Baked query to get states for specific entities."""
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, no_attributes, include_last_changed=True
    )
    # We got an include-list of entities, accelerate the query by filtering already
    # in the inner query.
    stmt += lambda q: q.where(
        States.state_id
        == (
            select(func.max(States.state_id).label("max_state_id"))
            .filter(
                (States.last_updated >= run_start)
                & (States.last_updated < utc_point_in_time)
            )
            .filter(States.entity_id.in_(entity_ids))
            .group_by(States.entity_id)
            .subquery()
        ).c.max_state_id
    )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    return stmt


def _generate_most_recent_states_by_date(
    run_start: datetime,
    utc_point_in_time: datetime,
) -> Subquery:
    """Generate the sub query for the most recent states by data."""
    return (
        select(
            States.entity_id.label("max_entity_id"),
            func.max(States.last_updated).label("max_last_updated"),
        )
        .filter(
            (States.last_updated >= run_start)
            & (States.last_updated < utc_point_in_time)
        )
        .group_by(States.entity_id)
        .subquery()
    )


def _get_states_for_all_stmt(
    schema_version: int,
    run_start: datetime,
    utc_point_in_time: datetime,
    filters: Filters | None,
    no_attributes: bool,
) -> StatementLambdaElement:
    """Baked query to get states for all entities."""
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, no_attributes, include_last_changed=True
    )
    # We did not get an include-list of entities, query all states in the inner
    # query, then filter out unwanted domains as well as applying the custom filter.
    # This filtering can't be done in the inner query because the domain column is
    # not indexed and we can't control what's in the custom filter.
    most_recent_states_by_date = _generate_most_recent_states_by_date(
        run_start, utc_point_in_time
    )
    stmt += lambda q: q.where(
        States.state_id
        == (
            select(func.max(States.state_id).label("max_state_id"))
            .join(
                most_recent_states_by_date,
                and_(
                    States.entity_id == most_recent_states_by_date.c.max_entity_id,
                    States.last_updated
                    == most_recent_states_by_date.c.max_last_updated,
                ),
            )
            .group_by(States.entity_id)
            .subquery()
        ).c.max_state_id,
    )
    stmt += _ignore_domains_filter
    if filters and filters.has_config:
        entity_filter = filters.states_entity_filter()
        stmt = stmt.add_criteria(lambda q: q.filter(entity_filter), track_on=[filters])
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    return stmt


def _get_rows_with_session(
    hass: HomeAssistant,
    session: Session,
    utc_point_in_time: datetime,
    entity_ids: list[str] | None = None,
    run: RecorderRuns | None = None,
    filters: Filters | None = None,
    no_attributes: bool = False,
) -> Iterable[Row]:
    """Return the states at a specific point in time."""
    schema_version = _schema_version(hass)
    if entity_ids and len(entity_ids) == 1:
        return execute_stmt_lambda_element(
            session,
            _get_single_entity_states_stmt(
                schema_version, utc_point_in_time, entity_ids[0], no_attributes
            ),
        )

    if run is None:
        run = recorder.get_instance(hass).run_history.get(utc_point_in_time)

    if run is None or process_timestamp(run.start) > utc_point_in_time:
        # History did not run before utc_point_in_time
        return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    if entity_ids:
        stmt = _get_states_for_entites_stmt(
            schema_version, run.start, utc_point_in_time, entity_ids, no_attributes
        )
    else:
        stmt = _get_states_for_all_stmt(
            schema_version, run.start, utc_point_in_time, filters, no_attributes
        )

    return execute_stmt_lambda_element(session, stmt)


def _get_single_entity_states_stmt(
    schema_version: int,
    utc_point_in_time: datetime,
    entity_id: str,
    no_attributes: bool = False,
) -> StatementLambdaElement:
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    stmt, join_attributes = lambda_stmt_and_join_attributes(
        schema_version, no_attributes, include_last_changed=True
    )
    stmt += (
        lambda q: q.filter(
            States.last_updated < utc_point_in_time,
            States.entity_id == entity_id,
        )
        .order_by(States.last_updated.desc())
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
    entity_ids: list[str] | None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    States must be sorted by entity_id and last_updated

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    if compressed_state_format:
        state_class = row_to_compressed_state
        _process_timestamp: Callable[
            [datetime], float | str
        ] = process_datetime_to_timestamp
        attr_time = COMPRESSED_STATE_LAST_UPDATED
        attr_state = COMPRESSED_STATE_STATE
    else:
        state_class = LazyState  # type: ignore[assignment]
        _process_timestamp = process_timestamp_to_utc_isoformat
        attr_time = LAST_CHANGED_KEY
        attr_state = STATE_KEY

    result: dict[str, list[State | dict[str, Any]]] = defaultdict(list)
    # Set all entity IDs to empty lists in result set to maintain the order
    if entity_ids is not None:
        for ent_id in entity_ids:
            result[ent_id] = []

    # Get the states at the start time
    timer_start = time.perf_counter()
    initial_states: dict[str, Row] = {}
    if include_start_time_state:
        initial_states = {
            row.entity_id: row
            for row in _get_rows_with_session(
                hass,
                session,
                start_time,
                entity_ids,
                filters=filters,
                no_attributes=no_attributes,
            )
        }

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug("getting %d first datapoints took %fs", len(result), elapsed)

    if entity_ids and len(entity_ids) == 1:
        states_iter: Iterable[tuple[str | Column, Iterator[States]]] = (
            (entity_ids[0], iter(states)),
        )
    else:
        states_iter = groupby(states, lambda state: state.entity_id)

    # Append all changes to it
    for ent_id, group in states_iter:
        attr_cache: dict[str, dict[str, Any]] = {}
        prev_state: Column | str
        ent_results = result[ent_id]
        if row := initial_states.pop(ent_id, None):
            prev_state = row.state
            ent_results.append(state_class(row, attr_cache, start_time))

        if not minimal_response or split_entity_id(ent_id)[0] in NEED_ATTRIBUTE_DOMAINS:
            ent_results.extend(state_class(db_state, attr_cache) for db_state in group)
            continue

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            if (first_state := next(group, None)) is None:
                continue
            prev_state = first_state.state
            ent_results.append(state_class(first_state, attr_cache))

        for row in group:
            # With minimal response we do not care about attribute
            # changes so we can filter out duplicate states
            if (state := row.state) == prev_state:
                continue

            ent_results.append(
                {
                    attr_state: state,
                    #
                    # minimal_response only makes sense with last_updated == last_updated
                    #
                    # We use last_updated for for last_changed since its the same
                    #
                    attr_time: _process_timestamp(row.last_updated),
                }
            )
            prev_state = state

    # If there are no states beyond the initial state,
    # the state a was never popped from initial_states
    for ent_id, row in initial_states.items():
        result[ent_id].append(state_class(row, {}, start_time))

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}
