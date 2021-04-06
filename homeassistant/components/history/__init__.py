"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime as dt, timedelta
from itertools import groupby
import json
import logging
import time
from typing import Iterable, cast

from aiohttp import web
from sqlalchemy import and_, bindparam, func, not_, or_
from sqlalchemy.ext import baked
import voluptuous as vol

from homeassistant.components import recorder
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder.models import (
    States,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    HTTP_BAD_REQUEST,
)
from homeassistant.core import Context, HomeAssistant, State, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    CONF_ENTITY_GLOBS,
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
)
import homeassistant.util.dt as dt_util

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "history"
CONF_ORDER = "use_include_order"

STATE_KEY = "state"
LAST_CHANGED_KEY = "last_changed"

GLOB_TO_SQL_CHARS = {
    42: "%",  # *
    46: "_",  # .
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {vol.Optional(CONF_ORDER, default=False): cv.boolean}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

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

HISTORY_BAKERY = "history_bakery"


def get_significant_states(hass, *args, **kwargs):
    """Wrap _get_significant_states with a sql session."""
    with session_scope(hass=hass) as session:
        return _get_significant_states(hass, session, *args, **kwargs)


def _get_significant_states(
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

    return _sorted_states_to_json(
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

        return _sorted_states_to_json(hass, session, states, start_time, entity_ids)


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

        return _sorted_states_to_json(
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

    # We have more than one entity to look at (most commonly we want
    # all entities,) so we need to do a search on all states since the
    # last recorder run started.
    query = session.query(*QUERY_STATES)

    most_recent_states_by_date = session.query(
        States.entity_id.label("max_entity_id"),
        func.max(States.last_updated).label("max_last_updated"),
    ).filter(
        (States.last_updated >= run.start) & (States.last_updated < utc_point_in_time)
    )

    if entity_ids:
        most_recent_states_by_date.filter(States.entity_id.in_(entity_ids))

    most_recent_states_by_date = most_recent_states_by_date.group_by(States.entity_id)

    most_recent_states_by_date = most_recent_states_by_date.subquery()

    most_recent_state_ids = session.query(
        func.max(States.state_id).label("max_state_id")
    ).join(
        most_recent_states_by_date,
        and_(
            States.entity_id == most_recent_states_by_date.c.max_entity_id,
            States.last_updated == most_recent_states_by_date.c.max_last_updated,
        ),
    )

    most_recent_state_ids = most_recent_state_ids.group_by(States.entity_id)

    most_recent_state_ids = most_recent_state_ids.subquery()

    query = query.join(
        most_recent_state_ids,
        States.state_id == most_recent_state_ids.c.max_state_id,
    )

    if entity_ids is not None:
        query = query.filter(States.entity_id.in_(entity_ids))
    else:
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


def _sorted_states_to_json(
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


async def async_setup(hass, config):
    """Set up the history hooks."""
    conf = config.get(DOMAIN, {})

    filters = sqlalchemy_filter_from_include_exclude_conf(conf)

    hass.data[HISTORY_BAKERY] = baked.bakery()

    use_include_order = conf.get(CONF_ORDER)

    hass.http.register_view(HistoryPeriodView(filters, use_include_order))
    hass.components.frontend.async_register_built_in_panel(
        "history", "history", "hass:poll-box"
    )

    return True


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = "/api/history/period"
    name = "api:history:view-period"
    extra_urls = ["/api/history/period/{datetime}"]

    def __init__(self, filters, use_include_order):
        """Initialize the history period view."""
        self.filters = filters
        self.use_include_order = use_include_order

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Return history over a period of time."""
        datetime_ = None
        if datetime:
            datetime_ = dt_util.parse_datetime(datetime)

            if datetime_ is None:
                return self.json_message("Invalid datetime", HTTP_BAD_REQUEST)

        now = dt_util.utcnow()

        one_day = timedelta(days=1)
        if datetime_:
            start_time = dt_util.as_utc(datetime_)
        else:
            start_time = now - one_day

        if start_time > now:
            return self.json([])

        end_time_str = request.query.get("end_time")
        if end_time_str:
            end_time = dt_util.parse_datetime(end_time_str)
            if end_time:
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message("Invalid end_time", HTTP_BAD_REQUEST)
        else:
            end_time = start_time + one_day
        entity_ids_str = request.query.get("filter_entity_id")
        entity_ids = None
        if entity_ids_str:
            entity_ids = entity_ids_str.lower().split(",")
        include_start_time_state = "skip_initial_state" not in request.query
        significant_changes_only = (
            request.query.get("significant_changes_only", "1") != "0"
        )

        minimal_response = "minimal_response" in request.query

        hass = request.app["hass"]

        if (
            not include_start_time_state
            and entity_ids
            and not _entities_may_have_state_changes_after(hass, entity_ids, start_time)
        ):
            return self.json([])

        return cast(
            web.Response,
            await hass.async_add_executor_job(
                self._sorted_significant_states_json,
                hass,
                start_time,
                end_time,
                entity_ids,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
            ),
        )

    def _sorted_significant_states_json(
        self,
        hass,
        start_time,
        end_time,
        entity_ids,
        include_start_time_state,
        significant_changes_only,
        minimal_response,
    ):
        """Fetch significant stats from the database as json."""
        timer_start = time.perf_counter()

        with session_scope(hass=hass) as session:
            result = _get_significant_states(
                hass,
                session,
                start_time,
                end_time,
                entity_ids,
                self.filters,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
            )

        result = list(result.values())
        if _LOGGER.isEnabledFor(logging.DEBUG):
            elapsed = time.perf_counter() - timer_start
            _LOGGER.debug("Extracted %d states in %fs", sum(map(len, result)), elapsed)

        # Optionally reorder the result to respect the ordering given
        # by any entities explicitly included in the configuration.
        if self.filters and self.use_include_order:
            sorted_result = []
            for order_entity in self.filters.included_entities:
                for state_list in result:
                    if state_list[0].entity_id == order_entity:
                        sorted_result.append(state_list)
                        result.remove(state_list)
                        break
            sorted_result.extend(result)
            result = sorted_result

        return self.json(result)


def sqlalchemy_filter_from_include_exclude_conf(conf):
    """Build a sql filter from config."""
    filters = Filters()
    exclude = conf.get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
        filters.excluded_entity_globs = exclude.get(CONF_ENTITY_GLOBS, [])
    include = conf.get(CONF_INCLUDE)
    if include:
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])
        filters.included_entity_globs = include.get(CONF_ENTITY_GLOBS, [])

    return filters if filters.has_config else None


class Filters:
    """Container for the configured include and exclude filters."""

    def __init__(self):
        """Initialise the include and exclude filters."""
        self.excluded_entities = []
        self.excluded_domains = []
        self.excluded_entity_globs = []

        self.included_entities = []
        self.included_domains = []
        self.included_entity_globs = []

    def apply(self, query):
        """Apply the entity filter."""
        if not self.has_config:
            return query

        return query.filter(self.entity_filter())

    @property
    def has_config(self):
        """Determine if there is any filter configuration."""
        if (
            self.excluded_entities
            or self.excluded_domains
            or self.excluded_entity_globs
            or self.included_entities
            or self.included_domains
            or self.included_entity_globs
        ):
            return True

        return False

    def bake(self, baked_query):
        """Update a baked query.

        Works the same as apply on a baked_query.
        """
        if not self.has_config:
            return

        baked_query += lambda q: q.filter(self.entity_filter())

    def entity_filter(self):
        """Generate the entity filter query."""
        includes = []
        if self.included_domains:
            includes.append(States.domain.in_(self.included_domains))
        if self.included_entities:
            includes.append(States.entity_id.in_(self.included_entities))
        for glob in self.included_entity_globs:
            includes.append(_glob_to_like(glob))

        excludes = []
        if self.excluded_domains:
            excludes.append(States.domain.in_(self.excluded_domains))
        if self.excluded_entities:
            excludes.append(States.entity_id.in_(self.excluded_entities))
        for glob in self.excluded_entity_globs:
            excludes.append(_glob_to_like(glob))

        if not includes and not excludes:
            return None

        if includes and not excludes:
            return or_(*includes)

        if not excludes and includes:
            return not_(or_(*excludes))

        return or_(*includes) & not_(or_(*excludes))


def _glob_to_like(glob_str):
    """Translate glob to sql."""
    return States.entity_id.like(glob_str.translate(GLOB_TO_SQL_CHARS))


def _entities_may_have_state_changes_after(
    hass: HomeAssistant, entity_ids: Iterable, start_time: dt
) -> bool:
    """Check the state machine to see if entities have changed since start time."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)

        if state is None or state.last_changed > start_time:
            return True

    return False


class LazyState(State):
    """A lazy version of core State."""

    __slots__ = [
        "_row",
        "entity_id",
        "state",
        "_attributes",
        "_last_changed",
        "_last_updated",
        "_context",
    ]

    def __init__(self, row):  # pylint: disable=super-init-not-called
        """Init the lazy state."""
        self._row = row
        self.entity_id = self._row.entity_id
        self.state = self._row.state or ""
        self._attributes = None
        self._last_changed = None
        self._last_updated = None
        self._context = None

    @property  # type: ignore
    def attributes(self):
        """State attributes."""
        if not self._attributes:
            try:
                self._attributes = json.loads(self._row.attributes)
            except ValueError:
                # When json.loads fails
                _LOGGER.exception("Error converting row to state: %s", self._row)
                self._attributes = {}
        return self._attributes

    @attributes.setter
    def attributes(self, value):
        """Set attributes."""
        self._attributes = value

    @property  # type: ignore
    def context(self):
        """State context."""
        if not self._context:
            self._context = Context(id=None)
        return self._context

    @context.setter
    def context(self, value):
        """Set context."""
        self._context = value

    @property  # type: ignore
    def last_changed(self):
        """Last changed datetime."""
        if not self._last_changed:
            self._last_changed = process_timestamp(self._row.last_changed)
        return self._last_changed

    @last_changed.setter
    def last_changed(self, value):
        """Set last changed datetime."""
        self._last_changed = value

    @property  # type: ignore
    def last_updated(self):
        """Last updated datetime."""
        if not self._last_updated:
            self._last_updated = process_timestamp(self._row.last_updated)
        return self._last_updated

    @last_updated.setter
    def last_updated(self, value):
        """Set last updated datetime."""
        self._last_updated = value

    def as_dict(self):
        """Return a dict representation of the LazyState.

        Async friendly.

        To be used for JSON serialization.
        """
        if self._last_changed:
            last_changed_isoformat = self._last_changed.isoformat()
        else:
            last_changed_isoformat = process_timestamp_to_utc_isoformat(
                self._row.last_changed
            )
        if self._last_updated:
            last_updated_isoformat = self._last_updated.isoformat()
        else:
            last_updated_isoformat = process_timestamp_to_utc_isoformat(
                self._row.last_updated
            )
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self._attributes or self.attributes,
            "last_changed": last_changed_isoformat,
            "last_updated": last_updated_isoformat,
        }

    def __eq__(self, other):
        """Return the comparison."""
        return (
            other.__class__ in [self.__class__, State]
            and self.entity_id == other.entity_id
            and self.state == other.state
            and self.attributes == other.attributes
        )
