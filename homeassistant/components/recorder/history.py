"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, MutableMapping
from datetime import datetime
from itertools import groupby
import logging
import time
from typing import Any, cast

from sqlalchemy import Column, Text, and_, bindparam, func, or_
from sqlalchemy.ext import baked
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal

from homeassistant.components import recorder
from homeassistant.core import HomeAssistant, State, split_entity_id
import homeassistant.util.dt as dt_util

from .models import (
    LazyState,
    RecorderRuns,
    StateAttributes,
    States,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from .util import execute, session_scope

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
BASE_STATES_NO_LAST_UPDATED = [
    States.entity_id,
    States.state,
    States.last_changed,
    literal(value=None, type_=Text).label("last_updated"),
]
QUERY_STATE_NO_ATTR = [
    *BASE_STATES,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATE_NO_ATTR_NO_LAST_UPDATED = [
    *BASE_STATES_NO_LAST_UPDATED,
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
QUERY_STATES_PRE_SCHEMA_25_NO_LAST_UPDATED = [
    *BASE_STATES_NO_LAST_UPDATED,
    States.attributes,
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATES = [
    *BASE_STATES,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
]
QUERY_STATES_NO_LAST_UPDATED = [
    *BASE_STATES_NO_LAST_UPDATED,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
]

HISTORY_BAKERY = "recorder_history_bakery"


def query_and_join_attributes(
    hass: HomeAssistant, no_attributes: bool
) -> tuple[list[Column], bool]:
    """Return the query keys and if StateAttributes should be joined."""
    # If no_attributes was requested we do the query
    # without the attributes fields and do not join the
    # state_attributes table
    if no_attributes:
        return QUERY_STATE_NO_ATTR, False
    # If we in the process of migrating schema we do
    # not want to join the state_attributes table as we
    # do not know if it will be there yet
    if recorder.get_instance(hass).migration_in_progress:
        return QUERY_STATES_PRE_SCHEMA_25, False
    # Finally if no migration is in progress and no_attributes
    # was not requested, we query both attributes columns and
    # join state_attributes
    return QUERY_STATES, True


def bake_query_and_join_attributes(
    hass: HomeAssistant, no_attributes: bool, include_last_updated: bool = True
) -> tuple[Any, bool]:
    """Return the initial backed query and if StateAttributes should be joined.

    Because these are baked queries the values inside the lambdas need
    to be explicitly written out to avoid caching the wrong values.
    """
    bakery: baked.bakery = hass.data[HISTORY_BAKERY]
    # If no_attributes was requested we do the query
    # without the attributes fields and do not join the
    # state_attributes table
    if no_attributes:
        if include_last_updated:
            return bakery(lambda session: session.query(*QUERY_STATE_NO_ATTR)), False
        return (
            bakery(lambda session: session.query(*QUERY_STATE_NO_ATTR_NO_LAST_UPDATED)),
            False,
        )
    # If we in the process of migrating schema we do
    # not want to join the state_attributes table as we
    # do not know if it will be there yet
    if recorder.get_instance(hass).migration_in_progress:
        if include_last_updated:
            return (
                bakery(lambda session: session.query(*QUERY_STATES_PRE_SCHEMA_25)),
                False,
            )
        return (
            bakery(
                lambda session: session.query(
                    *QUERY_STATES_PRE_SCHEMA_25_NO_LAST_UPDATED
                )
            ),
            False,
        )
    # Finally if no migration is in progress and no_attributes
    # was not requested, we query both attributes columns and
    # join state_attributes
    if include_last_updated:
        return bakery(lambda session: session.query(*QUERY_STATES)), True
    return bakery(lambda session: session.query(*QUERY_STATES_NO_LAST_UPDATED)), True


def async_setup(hass: HomeAssistant) -> None:
    """Set up the history hooks."""
    hass.data[HISTORY_BAKERY] = baked.bakery()


def get_significant_states(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Any | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
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
        )


def _query_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Any = None,
    significant_changes_only: bool = True,
    no_attributes: bool = False,
) -> list[States]:
    """Query the database for significant state changes."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        timer_start = time.perf_counter()

    baked_query, join_attributes = bake_query_and_join_attributes(hass, no_attributes)

    if entity_ids is not None and len(entity_ids) == 1:
        if (
            significant_changes_only
            and split_entity_id(entity_ids[0])[0] not in SIGNIFICANT_DOMAINS
        ):
            baked_query, join_attributes = bake_query_and_join_attributes(
                hass, no_attributes, include_last_updated=False
            )
            baked_query += lambda q: q.filter(
                States.last_changed == States.last_updated
            )
    elif significant_changes_only:
        baked_query += lambda q: q.filter(
            or_(
                *[
                    States.entity_id.like(entity_domain)
                    for entity_domain in SIGNIFICANT_DOMAINS_ENTITY_ID_LIKE
                ],
                (States.last_changed == States.last_updated),
            )
        )

    if entity_ids is not None:
        baked_query += lambda q: q.filter(
            States.entity_id.in_(bindparam("entity_ids", expanding=True))
        )
    else:
        baked_query += lambda q: q.filter(
            and_(
                *[
                    ~States.entity_id.like(entity_domain)
                    for entity_domain in IGNORE_DOMAINS_ENTITY_ID_LIKE
                ]
            )
        )
        if filters:
            filters.bake(baked_query)

    baked_query += lambda q: q.filter(States.last_updated > bindparam("start_time"))
    if end_time is not None:
        baked_query += lambda q: q.filter(States.last_updated < bindparam("end_time"))

    if join_attributes:
        baked_query += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    baked_query += lambda q: q.order_by(States.entity_id, States.last_updated)

    states = execute(
        baked_query(session).params(
            start_time=start_time, end_time=end_time, entity_ids=entity_ids
        )
    )

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug("get_significant_states took %fs", elapsed)

    return states


def get_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Any = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
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
    states = _query_significant_states_with_session(
        hass,
        session,
        start_time,
        end_time,
        entity_ids,
        filters,
        significant_changes_only,
        no_attributes,
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
    )


def get_full_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Any = None,
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
    with session_scope(hass=hass) as session:
        baked_query, join_attributes = bake_query_and_join_attributes(
            hass, no_attributes, include_last_updated=False
        )

        baked_query += lambda q: q.filter(
            (States.last_changed == States.last_updated)
            & (States.last_updated > bindparam("start_time"))
        )

        if end_time is not None:
            baked_query += lambda q: q.filter(
                States.last_updated < bindparam("end_time")
            )

        if entity_id is not None:
            baked_query += lambda q: q.filter_by(entity_id=bindparam("entity_id"))
            entity_id = entity_id.lower()

        if join_attributes:
            baked_query += lambda q: q.outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )

        if descending:
            baked_query += lambda q: q.order_by(
                States.entity_id, States.last_updated.desc()
            )
        else:
            baked_query += lambda q: q.order_by(States.entity_id, States.last_updated)

        if limit:
            baked_query += lambda q: q.limit(bindparam("limit"))

        states = execute(
            baked_query(session).params(
                start_time=start_time,
                end_time=end_time,
                entity_id=entity_id,
                limit=limit,
            )
        )

        entity_ids = [entity_id] if entity_id is not None else None

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


def get_last_state_changes(
    hass: HomeAssistant, number_of_states: int, entity_id: str
) -> MutableMapping[str, list[State]]:
    """Return the last number_of_states."""
    start_time = dt_util.utcnow()

    with session_scope(hass=hass) as session:
        baked_query, join_attributes = bake_query_and_join_attributes(
            hass, False, include_last_updated=False
        )

        baked_query += lambda q: q.filter(States.last_changed == States.last_updated)

        if entity_id is not None:
            baked_query += lambda q: q.filter_by(entity_id=bindparam("entity_id"))
            entity_id = entity_id.lower()

        if join_attributes:
            baked_query += lambda q: q.outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
        baked_query += lambda q: q.order_by(
            States.entity_id, States.last_updated.desc()
        )

        baked_query += lambda q: q.limit(bindparam("number_of_states"))

        states = execute(
            baked_query(session).params(
                number_of_states=number_of_states, entity_id=entity_id
            )
        )

        entity_ids = [entity_id] if entity_id is not None else None

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


def _get_states_with_session(
    hass: HomeAssistant,
    session: Session,
    utc_point_in_time: datetime,
    entity_ids: list[str] | None = None,
    run: RecorderRuns | None = None,
    filters: Any | None = None,
    no_attributes: bool = False,
) -> list[State]:
    """Return the states at a specific point in time."""
    if entity_ids and len(entity_ids) == 1:
        return _get_single_entity_states_with_session(
            hass, session, utc_point_in_time, entity_ids[0], no_attributes
        )

    if run is None:
        run = recorder.get_instance(hass).run_history.get(utc_point_in_time)

    if run is None or process_timestamp(run.start) > utc_point_in_time:
        # History did not run before utc_point_in_time
        return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    query_keys, join_attributes = query_and_join_attributes(hass, no_attributes)
    query = session.query(*query_keys)

    if entity_ids:
        # We got an include-list of entities, accelerate the query by filtering already
        # in the inner query.
        most_recent_state_ids = (
            session.query(
                func.max(States.state_id).label("max_state_id"),
            )
            .filter(
                (States.last_updated >= run.start)
                & (States.last_updated < utc_point_in_time)
            )
            .filter(States.entity_id.in_(entity_ids))
        )
        most_recent_state_ids = most_recent_state_ids.group_by(States.entity_id)
        most_recent_state_ids = most_recent_state_ids.subquery()
        query = query.join(
            most_recent_state_ids,
            States.state_id == most_recent_state_ids.c.max_state_id,
        )
        if join_attributes:
            query = query.outerjoin(
                StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
            )
    else:
        # We did not get an include-list of entities, query all states in the inner
        # query, then filter out unwanted domains as well as applying the custom filter.
        # This filtering can't be done in the inner query because the domain column is
        # not indexed and we can't control what's in the custom filter.
        most_recent_states_by_date = (
            session.query(
                States.entity_id.label("max_entity_id"),
                func.max(States.last_updated).label("max_last_updated"),
            )
            .filter(
                (States.last_updated >= run.start)
                & (States.last_updated < utc_point_in_time)
            )
            .group_by(States.entity_id)
            .subquery()
        )
        most_recent_state_ids = (
            session.query(func.max(States.state_id).label("max_state_id"))
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
        )
        query = query.join(
            most_recent_state_ids,
            States.state_id == most_recent_state_ids.c.max_state_id,
        )
        for entity_domain in IGNORE_DOMAINS_ENTITY_ID_LIKE:
            query = query.filter(~States.entity_id.like(entity_domain))
        if filters:
            query = filters.apply(query)
        if join_attributes:
            query = query.outerjoin(
                StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
            )

    attr_cache: dict[str, dict[str, Any]] = {}
    return [LazyState(row, attr_cache) for row in execute(query)]


def _get_single_entity_states_with_session(
    hass: HomeAssistant,
    session: Session,
    utc_point_in_time: datetime,
    entity_id: str,
    no_attributes: bool = False,
) -> list[State]:
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    baked_query, join_attributes = bake_query_and_join_attributes(hass, no_attributes)
    baked_query += lambda q: q.filter(
        States.last_updated < bindparam("utc_point_in_time"),
        States.entity_id == bindparam("entity_id"),
    )
    if join_attributes:
        baked_query += lambda q: q.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    baked_query += lambda q: q.order_by(States.last_updated.desc())
    baked_query += lambda q: q.limit(1)

    query = baked_query(session).params(
        utc_point_in_time=utc_point_in_time, entity_id=entity_id
    )

    return [LazyState(row) for row in execute(query)]


def _sorted_states_to_dict(
    hass: HomeAssistant,
    session: Session,
    states: Iterable[States],
    start_time: datetime,
    entity_ids: list[str] | None,
    filters: Any = None,
    include_start_time_state: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    States must be sorted by entity_id and last_updated

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    result: dict[str, list[State | dict[str, Any]]] = defaultdict(list)
    # Set all entity IDs to empty lists in result set to maintain the order
    if entity_ids is not None:
        for ent_id in entity_ids:
            result[ent_id] = []

    # Get the states at the start time
    timer_start = time.perf_counter()
    if include_start_time_state:
        for state in _get_states_with_session(
            hass,
            session,
            start_time,
            entity_ids,
            filters=filters,
            no_attributes=no_attributes,
        ):
            state.last_changed = start_time
            state.last_updated = start_time
            result[state.entity_id].append(state)

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug("getting %d first datapoints took %fs", len(result), elapsed)

    # Called in a tight loop so cache the function
    # here
    _process_timestamp_to_utc_isoformat = process_timestamp_to_utc_isoformat

    if entity_ids and len(entity_ids) == 1:
        states_iter: Iterable[tuple[str | Column, Iterator[States]]] = (
            (entity_ids[0], iter(states)),
        )
    else:
        states_iter = groupby(states, lambda state: state.entity_id)

    # Append all changes to it
    for ent_id, group in states_iter:
        ent_results = result[ent_id]
        attr_cache: dict[str, dict[str, Any]] = {}

        if not minimal_response or split_entity_id(ent_id)[0] in NEED_ATTRIBUTE_DOMAINS:
            ent_results.extend(LazyState(db_state, attr_cache) for db_state in group)
            continue

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            if (first_state := next(group, None)) is None:
                continue
            ent_results.append(LazyState(first_state, attr_cache))

        prev_state = ent_results[-1]
        assert isinstance(prev_state, LazyState)
        initial_state_count = len(ent_results)

        for db_state in group:
            # With minimal response we do not care about attribute
            # changes so we can filter out duplicate states
            if db_state.state == prev_state.state:
                continue

            ent_results.append(
                {
                    STATE_KEY: db_state.state,
                    LAST_CHANGED_KEY: _process_timestamp_to_utc_isoformat(
                        db_state.last_changed
                    ),
                }
            )
            prev_state = db_state

        if prev_state and len(ent_results) != initial_state_count:
            # There was at least one state change
            # replace the last minimal state with
            # a full state
            ent_results[-1] = LazyState(prev_state, attr_cache)

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}
