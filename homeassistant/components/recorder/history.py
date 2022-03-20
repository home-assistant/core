"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import groupby
import logging
import time

from sqlalchemy import Text, and_, bindparam, func, or_
from sqlalchemy.ext import baked
from sqlalchemy.sql.expression import literal

from homeassistant.components import recorder
from homeassistant.core import HomeAssistant, State, split_entity_id
import homeassistant.util.dt as dt_util

from .models import (
    LazyState,
    StateAttributes,
    States,
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
    States.domain,
    States.entity_id,
    States.state,
    States.last_changed,
    States.last_updated,
]
QUERY_STATE_NO_ATTR = [
    *BASE_STATES,
    literal(value=None, type_=Text).label("attributes"),
    literal(value=None, type_=Text).label("shared_attrs"),
]
QUERY_STATES = [
    *BASE_STATES,
    States.attributes,
    StateAttributes.shared_attrs,
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
    no_attributes=False,
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
    query_keys = QUERY_STATE_NO_ATTR if no_attributes else QUERY_STATES
    baked_query = hass.data[HISTORY_BAKERY](lambda session: session.query(*query_keys))

    if entity_ids is not None and len(entity_ids) == 1:
        if (
            significant_changes_only
            and split_entity_id(entity_ids[0])[0] not in SIGNIFICANT_DOMAINS
        ):
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

    if not no_attributes:
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
    with session_scope(hass=hass) as session:
        query_keys = QUERY_STATE_NO_ATTR if no_attributes else QUERY_STATES
        baked_query = hass.data[HISTORY_BAKERY](
            lambda session: session.query(*query_keys)
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

        if not no_attributes:
            baked_query += lambda q: q.outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )

        last_updated = States.last_updated.desc() if descending else States.last_updated
        baked_query += lambda q: q.order_by(States.entity_id, last_updated)

        if limit:
            baked_query += lambda q: q.limit(limit)

        states = execute(
            baked_query(session).params(
                start_time=start_time, end_time=end_time, entity_id=entity_id
            )
        )

        entity_ids = [entity_id] if entity_id is not None else None

        return _sorted_states_to_dict(
            hass,
            session,
            states,
            start_time,
            entity_ids,
            include_start_time_state=include_start_time_state,
        )


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

        return _sorted_states_to_dict(
            hass,
            session,
            reversed(states),
            start_time,
            entity_ids,
            include_start_time_state=False,
        )


def get_states(
    hass,
    utc_point_in_time,
    entity_ids=None,
    run=None,
    filters=None,
    no_attributes=False,
):
    """Return the states at a specific point in time."""
    if run is None:
        run = recorder.run_information_from_instance(hass, utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    with session_scope(hass=hass) as session:
        return _get_states_with_session(
            hass, session, utc_point_in_time, entity_ids, run, filters, no_attributes
        )


def _get_states_with_session(
    hass,
    session,
    utc_point_in_time,
    entity_ids=None,
    run=None,
    filters=None,
    no_attributes=False,
):
    """Return the states at a specific point in time."""
    if entity_ids and len(entity_ids) == 1:
        return _get_single_entity_states_with_session(
            hass, session, utc_point_in_time, entity_ids[0], no_attributes
        )

    if run is None:
        run = recorder.run_information_with_session(session, utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    query_keys = QUERY_STATE_NO_ATTR if no_attributes else QUERY_STATES
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
        if not no_attributes:
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
        if not no_attributes:
            query = query.outerjoin(
                StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
            )

    attr_cache = {}
    return [LazyState(row, attr_cache) for row in execute(query)]


def _get_single_entity_states_with_session(
    hass, session, utc_point_in_time, entity_id, no_attributes=False
):
    # Use an entirely different (and extremely fast) query if we only
    # have a single entity id
    query_keys = QUERY_STATE_NO_ATTR if no_attributes else QUERY_STATES
    baked_query = hass.data[HISTORY_BAKERY](lambda session: session.query(*query_keys))
    baked_query += lambda q: q.filter(
        States.last_updated < bindparam("utc_point_in_time"),
        States.entity_id == bindparam("entity_id"),
    )
    if not no_attributes:
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
    hass,
    session,
    states,
    start_time,
    entity_ids,
    filters=None,
    include_start_time_state=True,
    minimal_response=False,
    no_attributes=False,
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
            hass,
            session,
            start_time,
            entity_ids,
            run=run,
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

    # Append all changes to it
    for ent_id, group in groupby(states, lambda state: state.entity_id):
        domain = split_entity_id(ent_id)[0]
        ent_results = result[ent_id]
        attr_cache = {}

        if not minimal_response or domain in NEED_ATTRIBUTE_DOMAINS:
            ent_results.extend(LazyState(db_state, attr_cache) for db_state in group)

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            ent_results.append(LazyState(next(group), attr_cache))

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
            ent_results[-1] = LazyState(prev_state, attr_cache)

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}


def get_state(hass, utc_point_in_time, entity_id, run=None, no_attributes=False):
    """Return a state at a specific point in time."""
    states = get_states(hass, utc_point_in_time, (entity_id,), run, None, no_attributes)
    return states[0] if states else None
