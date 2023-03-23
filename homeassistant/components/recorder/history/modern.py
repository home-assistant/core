"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, MutableMapping
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from typing import Any, cast

from sqlalchemy import Column, and_, func, lambda_stmt, or_, select
from sqlalchemy.engine.row import Row
from sqlalchemy.orm.properties import MappedColumn
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.const import COMPRESSED_STATE_LAST_UPDATED, COMPRESSED_STATE_STATE
from homeassistant.core import HomeAssistant, State, split_entity_id
import homeassistant.util.dt as dt_util

from ... import recorder
from ..db_schema import RecorderRuns, StateAttributes, States, StatesMeta
from ..filters import Filters
from ..models import (
    LazyState,
    extract_metadata_ids,
    process_timestamp,
    row_to_compressed_state,
)
from ..util import execute_stmt_lambda_element, session_scope
from .const import (
    IGNORE_DOMAINS_ENTITY_ID_LIKE,
    LAST_CHANGED_KEY,
    NEED_ATTRIBUTE_DOMAINS,
    SIGNIFICANT_DOMAINS,
    SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE,
    STATE_KEY,
)

_BASE_STATES = (
    States.metadata_id,
    States.state,
    States.last_changed_ts,
    States.last_updated_ts,
)
_BASE_STATES_NO_LAST_CHANGED = (  # type: ignore[var-annotated]
    States.metadata_id,
    States.state,
    literal(value=None).label("last_changed_ts"),
    States.last_updated_ts,
)
_QUERY_STATE_NO_ATTR = (*_BASE_STATES,)
_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED = (*_BASE_STATES_NO_LAST_CHANGED,)
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
) -> MutableMapping[str, list[State | dict[str, Any]]]:
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


def _ignore_domains_filter(query: Query) -> Query:
    """Add a filter to ignore domains we do not fetch history for."""
    return query.filter(
        and_(
            *[
                ~StatesMeta.entity_id.like(entity_domain)
                for entity_domain in IGNORE_DOMAINS_ENTITY_ID_LIKE
            ]
        )
    )


def _significant_states_stmt(
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
    metadata_ids_in_significant_domains: list[int],
    filters: Filters | None,
    significant_changes_only: bool,
    no_attributes: bool,
) -> StatementLambdaElement:
    """Query the database for significant state changes."""
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=not significant_changes_only
    )
    join_states_meta = False
    if metadata_ids and significant_changes_only:
        # Since we are filtering on entity_id (metadata_id) we can avoid
        # the join of the states_meta table since we already know which
        # metadata_ids are in the significant domains.
        stmt += lambda q: q.filter(
            States.metadata_id.in_(metadata_ids_in_significant_domains)
            | (States.last_changed_ts == States.last_updated_ts)
            | States.last_changed_ts.is_(None)
        )
    elif significant_changes_only:
        # This is the case where we are not filtering on entity_id
        # so we need to join the states_meta table to filter out
        # the domains we do not care about. This query path was
        # only used by the old history page to show all entities
        # in the UI. The new history page filters on entity_id
        # so this query path is not used anymore except for third
        # party integrations that use the history API.
        stmt += lambda q: q.filter(
            or_(
                *[
                    StatesMeta.entity_id.like(entity_domain)
                    for entity_domain in SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE
                ],
                (
                    (States.last_changed_ts == States.last_updated_ts)
                    | States.last_changed_ts.is_(None)
                ),
            )
        )
        join_states_meta = True

    if metadata_ids:
        stmt += lambda q: q.filter(
            # https://github.com/python/mypy/issues/2608
            States.metadata_id.in_(metadata_ids)  # type:ignore[arg-type]
        )
    else:
        stmt += _ignore_domains_filter
        if filters and filters.has_config:
            entity_filter = filters.states_metadata_entity_filter()
            stmt = stmt.add_criteria(
                lambda q: q.filter(entity_filter), track_on=[filters]
            )
        join_states_meta = True

    start_time_ts = start_time.timestamp()
    stmt += lambda q: q.filter(States.last_updated_ts > start_time_ts)
    if end_time:
        end_time_ts = end_time.timestamp()
        stmt += lambda q: q.filter(States.last_updated_ts < end_time_ts)
    if join_states_meta:
        stmt += lambda q: q.outerjoin(
            StatesMeta, States.metadata_id == StatesMeta.metadata_id
        )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    stmt += lambda q: q.order_by(States.metadata_id, States.last_updated_ts)
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
    """Return states changes during UTC period start_time - end_time.

    entity_ids is an optional iterable of entities to include in the results.

    filters is an optional SQLAlchemy filter which will be applied to the database
    queries unless entity_ids is given, in which case its ignored.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    metadata_ids: list[int] | None = None
    entity_id_to_metadata_id: dict[str, int | None] | None = None
    metadata_ids_in_significant_domains: list[int] = []
    if entity_ids:
        instance = recorder.get_instance(hass)
        if not (
            entity_id_to_metadata_id := instance.states_meta_manager.get_many(
                entity_ids, session, False
            )
        ) or not (metadata_ids := extract_metadata_ids(entity_id_to_metadata_id)):
            return {}
        if significant_changes_only:
            metadata_ids_in_significant_domains = [
                metadata_id
                for entity_id, metadata_id in entity_id_to_metadata_id.items()
                if metadata_id is not None
                and split_entity_id(entity_id)[0] in SIGNIFICANT_DOMAINS
            ]
    stmt = _significant_states_stmt(
        start_time,
        end_time,
        metadata_ids,
        metadata_ids_in_significant_domains,
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
        entity_id_to_metadata_id,
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
    """Variant of get_significant_states_with_session.

    Difference with get_significant_states_with_session is that it does not
    return minimal responses.
    """
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
    start_time: datetime,
    end_time: datetime | None,
    metadata_id: int | None,
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
    if metadata_id:
        stmt += lambda q: q.filter(States.metadata_id == metadata_id)
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    if descending:
        stmt += lambda q: q.order_by(States.metadata_id, States.last_updated_ts.desc())
    else:
        stmt += lambda q: q.order_by(States.metadata_id, States.last_updated_ts)
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

    with session_scope(hass=hass, read_only=True) as session:
        metadata_id: int | None = None
        entity_id_to_metadata_id = None
        if entity_id:
            instance = recorder.get_instance(hass)
            metadata_id = instance.states_meta_manager.get(entity_id, session, False)
            entity_id_to_metadata_id = {entity_id: metadata_id}
        stmt = _state_changed_during_period_stmt(
            start_time,
            end_time,
            metadata_id,
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
                entity_id_to_metadata_id,
                include_start_time_state=include_start_time_state,
            ),
        )


def _get_last_state_changes_stmt(
    number_of_states: int, metadata_id: int
) -> StatementLambdaElement:
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        False, include_last_changed=False
    )
    stmt += lambda q: q.where(
        States.state_id
        == (
            select(States.state_id)
            .filter(States.metadata_id == metadata_id)
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
) -> MutableMapping[str, list[State]]:
    """Return the last number_of_states."""
    entity_id_lower = entity_id.lower()
    entity_ids = [entity_id_lower]

    with session_scope(hass=hass, read_only=True) as session:
        instance = recorder.get_instance(hass)
        if not (
            metadata_id := instance.states_meta_manager.get(entity_id, session, False)
        ):
            return {}
        entity_id_to_metadata_id: dict[str, int | None] = {entity_id_lower: metadata_id}
        stmt = _get_last_state_changes_stmt(number_of_states, metadata_id)
        states = list(execute_stmt_lambda_element(session, stmt))
        return cast(
            MutableMapping[str, list[State]],
            _sorted_states_to_dict(
                hass,
                session,
                reversed(states),
                dt_util.utcnow(),
                entity_ids,
                entity_id_to_metadata_id,
                include_start_time_state=False,
            ),
        )


def _get_states_for_entities_stmt(
    run_start: datetime,
    utc_point_in_time: datetime,
    metadata_ids: list[int],
    no_attributes: bool,
) -> StatementLambdaElement:
    """Baked query to get states for specific entities."""
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=True
    )
    # We got an include-list of entities, accelerate the query by filtering already
    # in the inner query.
    run_start_ts = process_timestamp(run_start).timestamp()
    utc_point_in_time_ts = dt_util.utc_to_timestamp(utc_point_in_time)
    stmt += lambda q: q.join(
        (
            most_recent_states_for_entities_by_date := (
                select(
                    States.metadata_id.label("max_metadata_id"),
                    # https://github.com/sqlalchemy/sqlalchemy/issues/9189
                    # pylint: disable-next=not-callable
                    func.max(States.last_updated_ts).label("max_last_updated"),
                )
                .filter(
                    (States.last_updated_ts >= run_start_ts)
                    & (States.last_updated_ts < utc_point_in_time_ts)
                )
                .filter(States.metadata_id.in_(metadata_ids))
                .group_by(States.metadata_id)
                .subquery()
            )
        ),
        and_(
            States.metadata_id
            == most_recent_states_for_entities_by_date.c.max_metadata_id,
            States.last_updated_ts
            == most_recent_states_for_entities_by_date.c.max_last_updated,
        ),
    )
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    return stmt


def _get_states_for_all_stmt(
    run_start: datetime,
    utc_point_in_time: datetime,
    filters: Filters | None,
    no_attributes: bool,
) -> StatementLambdaElement:
    """Baked query to get states for all entities."""
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=True
    )
    # We did not get an include-list of entities, query all states in the inner
    # query, then filter out unwanted domains as well as applying the custom filter.
    # This filtering can't be done in the inner query because the domain column is
    # not indexed and we can't control what's in the custom filter.
    run_start_ts = process_timestamp(run_start).timestamp()
    utc_point_in_time_ts = dt_util.utc_to_timestamp(utc_point_in_time)
    stmt += lambda q: q.join(
        (
            most_recent_states_by_date := (
                select(
                    States.metadata_id.label("max_metadata_id"),
                    # https://github.com/sqlalchemy/sqlalchemy/issues/9189
                    # pylint: disable-next=not-callable
                    func.max(States.last_updated_ts).label("max_last_updated"),
                )
                .filter(
                    (States.last_updated_ts >= run_start_ts)
                    & (States.last_updated_ts < utc_point_in_time_ts)
                )
                .group_by(States.metadata_id)
                .subquery()
            )
        ),
        and_(
            States.metadata_id == most_recent_states_by_date.c.max_metadata_id,
            States.last_updated_ts == most_recent_states_by_date.c.max_last_updated,
        ),
    )
    stmt += _ignore_domains_filter
    if filters and filters.has_config:
        entity_filter = filters.states_metadata_entity_filter()
        stmt = stmt.add_criteria(lambda q: q.filter(entity_filter), track_on=[filters])
    if join_attributes:
        stmt += lambda q: q.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    stmt += lambda q: q.outerjoin(
        StatesMeta, States.metadata_id == StatesMeta.metadata_id
    )
    return stmt


def _get_rows_with_session(
    hass: HomeAssistant,
    session: Session,
    utc_point_in_time: datetime,
    entity_ids: list[str] | None = None,
    entity_id_to_metadata_id: dict[str, int | None] | None = None,
    run: RecorderRuns | None = None,
    filters: Filters | None = None,
    no_attributes: bool = False,
) -> Iterable[Row]:
    """Return the states at a specific point in time."""
    if entity_ids and len(entity_ids) == 1:
        if not entity_id_to_metadata_id or not (
            metadata_id := entity_id_to_metadata_id.get(entity_ids[0])
        ):
            return []
        return execute_stmt_lambda_element(
            session,
            _get_single_entity_states_stmt(
                utc_point_in_time, metadata_id, no_attributes
            ),
        )

    if run is None:
        run = recorder.get_instance(hass).recorder_runs_manager.get(utc_point_in_time)

    if run is None or process_timestamp(run.start) > utc_point_in_time:
        # History did not run before utc_point_in_time
        return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    if entity_ids:
        if not entity_id_to_metadata_id or not (
            metadata_ids := extract_metadata_ids(entity_id_to_metadata_id)
        ):
            return []
        stmt = _get_states_for_entities_stmt(
            run.start, utc_point_in_time, metadata_ids, no_attributes
        )
    else:
        stmt = _get_states_for_all_stmt(
            run.start, utc_point_in_time, filters, no_attributes
        )

    return execute_stmt_lambda_element(session, stmt)


def _get_single_entity_states_stmt(
    utc_point_in_time: datetime,
    metadata_id: int,
    no_attributes: bool = False,
) -> StatementLambdaElement:
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    stmt, join_attributes = _lambda_stmt_and_join_attributes(
        no_attributes, include_last_changed=True
    )
    utc_point_in_time_ts = dt_util.utc_to_timestamp(utc_point_in_time)
    stmt += (
        lambda q: q.filter(
            States.last_updated_ts < utc_point_in_time_ts,
            States.metadata_id == metadata_id,
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
    entity_ids: list[str] | None,
    entity_id_to_metadata_id: dict[str, int | None] | None,
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
    field_map = _FIELD_MAP
    state_class: Callable[
        [Row, dict[str, dict[str, Any]], datetime | None], State | dict[str, Any]
    ]
    if compressed_state_format:
        state_class = row_to_compressed_state
        attr_time = COMPRESSED_STATE_LAST_UPDATED
        attr_state = COMPRESSED_STATE_STATE
    else:
        state_class = LazyState
        attr_time = LAST_CHANGED_KEY
        attr_state = STATE_KEY

    result: dict[str, list[State | dict[str, Any]]] = defaultdict(list)
    metadata_id_to_entity_id: dict[int, str] = {}
    metadata_id_idx = field_map["metadata_id"]

    # Set all entity IDs to empty lists in result set to maintain the order
    if entity_ids is not None:
        for ent_id in entity_ids:
            result[ent_id] = []

        if entity_id_to_metadata_id:
            metadata_id_to_entity_id = {
                v: k for k, v in entity_id_to_metadata_id.items() if v is not None
            }
    else:
        metadata_id_to_entity_id = recorder.get_instance(
            hass
        ).states_meta_manager.get_metadata_id_to_entity_id(session)

    # Get the states at the start time
    initial_states: dict[int, Row] = {}
    if include_start_time_state:
        initial_states = {
            row[metadata_id_idx]: row
            for row in _get_rows_with_session(
                hass,
                session,
                start_time,
                entity_ids,
                entity_id_to_metadata_id,
                filters=filters,
                no_attributes=no_attributes,
            )
        }

    if entity_ids and len(entity_ids) == 1:
        if not entity_id_to_metadata_id or not (
            metadata_id := entity_id_to_metadata_id.get(entity_ids[0])
        ):
            return {}
        states_iter: Iterable[tuple[int, Iterator[Row]]] = (
            (metadata_id, iter(states)),
        )
    else:
        key_func = itemgetter(metadata_id_idx)
        states_iter = groupby(states, key_func)

    # Append all changes to it
    for metadata_id, group in states_iter:
        attr_cache: dict[str, dict[str, Any]] = {}
        prev_state: Column | str | None = None
        if not (entity_id := metadata_id_to_entity_id.get(metadata_id)):
            continue
        ent_results = result[entity_id]
        if row := initial_states.pop(metadata_id, None):
            prev_state = row.state
            ent_results.append(state_class(row, attr_cache, start_time, entity_id=entity_id))  # type: ignore[call-arg]

        if (
            not minimal_response
            or split_entity_id(entity_id)[0] in NEED_ATTRIBUTE_DOMAINS
        ):
            ent_results.extend(
                state_class(db_state, attr_cache, None, entity_id=entity_id)  # type: ignore[call-arg]
                for db_state in group
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
            ent_results.append(
                state_class(first_state, attr_cache, None, entity_id=entity_id)  # type: ignore[call-arg]
            )

        state_idx = field_map["state"]
        last_updated_ts_idx = field_map["last_updated_ts"]

        #
        # minimal_response only makes sense with last_updated == last_updated
        #
        # We use last_updated for for last_changed since its the same
        #
        # With minimal response we do not care about attribute
        # changes so we can filter out duplicate states
        if compressed_state_format:
            # Compressed state format uses the timestamp directly
            ent_results.extend(
                {
                    attr_state: (prev_state := state),
                    attr_time: row[last_updated_ts_idx],
                }
                for row in group
                if (state := row[state_idx]) != prev_state
            )
            continue

        # Non-compressed state format returns an ISO formatted string
        _utc_from_timestamp = dt_util.utc_from_timestamp
        ent_results.extend(
            {
                attr_state: (prev_state := state),  # noqa: F841
                attr_time: _utc_from_timestamp(row[last_updated_ts_idx]).isoformat(),
            }
            for row in group
            if (state := row[state_idx]) != prev_state
        )

    # If there are no states beyond the initial state,
    # the state a was never popped from initial_states
    for metadata_id, row in initial_states.items():
        if entity_id := metadata_id_to_entity_id.get(metadata_id):
            result[entity_id].append(
                state_class(row, {}, start_time, entity_id=entity_id)  # type: ignore[call-arg]
            )

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}
