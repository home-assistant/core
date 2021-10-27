"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from itertools import groupby
import logging
import time

from sqlalchemy import and_, bindparam, func
from sqlalchemy.ext import baked

from homeassistant.components import recorder
from homeassistant.components.recorder.models import (
    States,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.core import split_entity_id
import homeassistant.util.dt as dt_util

from .models import LazyState

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

STATE_KEY = "state"
LAST_CHANGED_KEY = "last_changed"

SIGNIFICANT_DOMAINS = (
    "climate",
    "device_tracker",
    "humidifier",
    "thermostat",
    "water_heater",
)
IGNORE_DOMAINS = ("zone", "scene")
NEED_ATTRIBUTE_DOMAINS = {
    "climate",
    "humidifier",
    "input_datetime",
    "thermostat",
    "water_heater",
}

QUERY_STATES = [
    States.domain,
    States.entity_id,
    States.state,
    States.attributes,
    States.last_changed,
    States.last_updated,
]

HISTORY_BAKERY = "recorder_history_bakery"


def async_setup(hass):
    """Set up the history hooks."""
    hass.data[HISTORY_BAKERY] = baked.bakery()


def get_significant_states(hass, *args, **kwargs):
    """Wrap get_significant_states_with_session with an sql session."""
    with session_scope(hass=hass) as session:
        return get_significant_states_with_session(hass, session, *args, **kwargs)


def get_significant_states_with_session(
    hass,
    session,
    start_time,
    end_time=None,
    entity_ids=None,
    filters=None,
    include_start_time_state=True,
    significant_changes_only=True,
    minimal_response=False,
):
    """
    Return states changes during UTC period start_time - end_time.

    entity_ids is an optional iterable of entities to include in the results.

    filters is an optional SQLAlchemy filter which will be applied to the database
    queries unless entity_ids is given, in which case its ignored.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    timer_start = time.perf_counter()

    baked_query = hass.data[HISTORY_BAKERY](
        lambda session: session.query(*QUERY_STATES)
    )

    if significant_changes_only:
        baked_query += lambda q: q.filter(
            (
                States.domain.in_(SIGNIFICANT_DOMAINS)
                | (States.last_changed == States.last_updated)
            )
            & (States.last_updated > bindparam("start_time"))
        )
    else:
        baked_query += lambda q: q.filter(States.last_updated > bindparam("start_time"))

    if entity_ids is not None:
        baked_query += lambda q: q.filter(
            States.entity_id.in_(bindparam("entity_ids", expanding=True))
        )
    else:
        baked_query += lambda q: q.filter(~States.domain.in_(IGNORE_DOMAINS))
        if filters:
            filters.bake(baked_query)

    if end_time is not None:
        baked_query += lambda q: q.filter(States.last_updated < bindparam("end_time"))

    baked_query += lambda q: q.order_by(States.entity_id, States.last_updated)

    states = execute(
        baked_query(session).params(
            start_time=start_time, end_time=end_time, entity_ids=entity_ids
        )
    )

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug("get_significant_states took %fs", elapsed)

    return _sorted_states_to_dict(
        hass,
        session,
        states,
        start_time,
        entity_ids,
        filters,
        include_start_time_state,
        minimal_response,
    )


def state_changes_during_period(hass, start_time, end_time=None, entity_id=None):
    """Return states changes during UTC period start_time - end_time."""
    with session_scope(hass=hass) as session:
        baked_query = hass.data[HISTORY_BAKERY](
            lambda session: session.query(*QUERY_STATES)
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

        baked_query += lambda q: q.order_by(States.entity_id, States.last_updated)

        states = execute(
            baked_query(session).params(
                start_time=start_time, end_time=end_time, entity_id=entity_id
            )
        )

        entity_ids = [entity_id] if entity_id is not None else None

        return _sorted_states_to_dict(hass, session, states, start_time, entity_ids)


def get_last_state_changes(hass, number_of_states, entity_id):
    """Return the last number_of_states."""
    start_time = dt_util.utcnow()

    with session_scope(hass=hass) as session:
        baked_query = hass.data[HISTORY_BAKERY](
            lambda session: session.query(*QUERY_STATES)
        )
        baked_query += lambda q: q.filter(States.last_changed == States.last_updated)

        if entity_id is not None:
            baked_query += lambda q: q.filter_by(entity_id=bindparam("entity_id"))
            entity_id = entity_id.lower()

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

        return _sorted_states_to_dict(
            hass,
            session,
            reversed(states),
            start_time,
            entity_ids,
            include_start_time_state=False,
        )


def get_states(hass, utc_point_in_time, entity_ids=None, run=None, filters=None):
    """Return the states at a specific point in time."""
    if run is None:
        run = recorder.run_information_from_instance(hass, utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    with session_scope(hass=hass) as session:
        return _get_states_with_session(
            hass, session, utc_point_in_time, entity_ids, run, filters
        )


def _get_states_with_session(
    hass, session, utc_point_in_time, entity_ids=None, run=None, filters=None
):
    """Return the states at a specific point in time."""
    if entity_ids and len(entity_ids) == 1:
        return _get_single_entity_states_with_session(
            hass, session, utc_point_in_time, entity_ids[0]
        )

    if run is None:
        run = recorder.run_information_with_session(session, utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    query = session.query(*QUERY_STATES)

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
        query = query.filter(~States.domain.in_(IGNORE_DOMAINS))
        if filters:
            query = filters.apply(query)

    return [LazyState(row) for row in execute(query)]


def _get_single_entity_states_with_session(hass, session, utc_point_in_time, entity_id):
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    baked_query = hass.data[HISTORY_BAKERY](
        lambda session: session.query(*QUERY_STATES)
    )
    baked_query += lambda q: q.filter(
        States.last_updated < bindparam("utc_point_in_time"),
        States.entity_id == bindparam("entity_id"),
    )
    baked_query += lambda q: q.order_by(States.last_updated.desc())
    baked_query += lambda q: q.limit(1)

    query = baked_query(session).params(
        utc_point_in_time=utc_point_in_time, entity_id=entity_id
    )

    return [LazyState(row) for row in execute(query)]


def _sorted_states_to_dict(
    hass,
    session,
    states,
    start_time,
    entity_ids,
    filters=None,
    include_start_time_state=True,
    minimal_response=False,
):
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    States must be sorted by entity_id and last_updated

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    result = defaultdict(list)
    # Set all entity IDs to empty lists in result set to maintain the order
    if entity_ids is not None:
        for ent_id in entity_ids:
            result[ent_id] = []

    # Get the states at the start time
    timer_start = time.perf_counter()
    if include_start_time_state:
        run = recorder.run_information_from_instance(hass, start_time)
        for state in _get_states_with_session(
            hass, session, start_time, entity_ids, run=run, filters=filters
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

    # Append all changes to it
    for ent_id, group in groupby(states, lambda state: state.entity_id):
        domain = split_entity_id(ent_id)[0]
        ent_results = result[ent_id]
        if not minimal_response or domain in NEED_ATTRIBUTE_DOMAINS:
            ent_results.extend(LazyState(db_state) for db_state in group)

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            ent_results.append(LazyState(next(group)))

        prev_state = ent_results[-1]
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
            ent_results[-1] = LazyState(prev_state)

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}


def get_state(hass, utc_point_in_time, entity_id, run=None):
    """Return a state at a specific point in time."""
    states = get_states(hass, utc_point_in_time, (entity_id,), run)
    return states[0] if states else None
