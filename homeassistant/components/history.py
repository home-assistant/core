"""
Provide pre-made queries on top of the recorder component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/history/
"""
import asyncio
from collections import defaultdict
from datetime import timedelta
from itertools import groupby
import logging
import time

import voluptuous as vol

from homeassistant.const import (
    HTTP_BAD_REQUEST, CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE)
import homeassistant.util.dt as dt_util
from homeassistant.components import recorder, script
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_HIDDEN
from homeassistant.components.recorder.util import session_scope, execute
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']

CONF_ORDER = 'use_include_order'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: recorder.FILTER_SCHEMA.extend({
        vol.Optional(CONF_ORDER, default=False): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

SIGNIFICANT_DOMAINS = ('thermostat', 'climate')
IGNORE_DOMAINS = ('zone', 'scene',)


def last_recorder_run(hass):
    """Retrieve the last closed recorder run from the database."""
    from homeassistant.components.recorder.models import RecorderRuns

    with session_scope(hass=hass) as session:
        res = (session.query(RecorderRuns)
               .filter(RecorderRuns.end.isnot(None))
               .order_by(RecorderRuns.end.desc()).first())
        if res is None:
            return None
        session.expunge(res)
        return res


def get_significant_states(hass, start_time, end_time=None, entity_ids=None,
                           filters=None, include_start_time_state=True):
    """
    Return states changes during UTC period start_time - end_time.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    timer_start = time.perf_counter()
    from homeassistant.components.recorder.models import States

    with session_scope(hass=hass) as session:
        query = session.query(States).filter(
            (States.domain.in_(SIGNIFICANT_DOMAINS) |
             (States.last_changed == States.last_updated)) &
            (States.last_updated > start_time))

        if filters:
            query = filters.apply(query, entity_ids)

        if end_time is not None:
            query = query.filter(States.last_updated < end_time)

        query = query.order_by(States.last_updated)

        states = (
            state for state in execute(query)
            if (_is_significant(state) and
                not state.attributes.get(ATTR_HIDDEN, False)))

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug(
            'get_significant_states took %fs', elapsed)

    return states_to_json(
        hass, states, start_time, entity_ids, filters,
        include_start_time_state)


def state_changes_during_period(hass, start_time, end_time=None,
                                entity_id=None):
    """Return states changes during UTC period start_time - end_time."""
    from homeassistant.components.recorder.models import States

    with session_scope(hass=hass) as session:
        query = session.query(States).filter(
            (States.last_changed == States.last_updated) &
            (States.last_updated > start_time))

        if end_time is not None:
            query = query.filter(States.last_updated < end_time)

        if entity_id is not None:
            query = query.filter_by(entity_id=entity_id.lower())

        entity_ids = [entity_id] if entity_id is not None else None

        states = execute(
            query.order_by(States.last_updated))

    return states_to_json(hass, states, start_time, entity_ids)


def get_states(hass, utc_point_in_time, entity_ids=None, run=None,
               filters=None):
    """Return the states at a specific point in time."""
    from homeassistant.components.recorder.models import States

    if run is None:
        run = recorder.run_information(hass, utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    from sqlalchemy import and_, func

    with session_scope(hass=hass) as session:
        if entity_ids and len(entity_ids) == 1:
            # Use an entirely different (and extremely fast) query if we only
            # have a single entity id
            most_recent_state_ids = session.query(
                States.state_id.label('max_state_id')
            ).filter(
                (States.last_updated < utc_point_in_time) &
                (States.entity_id.in_(entity_ids))
            ).order_by(
                States.last_updated.desc())

            most_recent_state_ids = most_recent_state_ids.limit(1)

        else:
            # We have more than one entity to look at (most commonly we want
            # all entities,) so we need to do a search on all states since the
            # last recorder run started.

            most_recent_states_by_date = session.query(
                States.entity_id.label('max_entity_id'),
                func.max(States.last_updated).label('max_last_updated')
            ).filter(
                (States.last_updated >= run.start) &
                (States.last_updated < utc_point_in_time)
            )

            if entity_ids:
                most_recent_states_by_date.filter(
                    States.entity_id.in_(entity_ids))

            most_recent_states_by_date = most_recent_states_by_date.group_by(
                States.entity_id)

            most_recent_states_by_date = most_recent_states_by_date.subquery()

            most_recent_state_ids = session.query(
                func.max(States.state_id).label('max_state_id')
            ).join(most_recent_states_by_date, and_(
                States.entity_id == most_recent_states_by_date.c.max_entity_id,
                States.last_updated == most_recent_states_by_date.c.
                max_last_updated))

            most_recent_state_ids = most_recent_state_ids.group_by(
                States.entity_id)

        most_recent_state_ids = most_recent_state_ids.subquery()

        query = session.query(States).join(
            most_recent_state_ids,
            States.state_id == most_recent_state_ids.c.max_state_id
        ).filter((~States.domain.in_(IGNORE_DOMAINS)))

        if filters:
            query = filters.apply(query, entity_ids)

        return [state for state in execute(query)
                if not state.attributes.get(ATTR_HIDDEN, False)]


def states_to_json(
        hass,
        states,
        start_time,
        entity_ids,
        filters=None,
        include_start_time_state=True):
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    result = defaultdict(list)

    # Get the states at the start time
    timer_start = time.perf_counter()
    if include_start_time_state:
        for state in get_states(hass, start_time, entity_ids, filters=filters):
            state.last_changed = start_time
            state.last_updated = start_time
            result[state.entity_id].append(state)

    if _LOGGER.isEnabledFor(logging.DEBUG):
        elapsed = time.perf_counter() - timer_start
        _LOGGER.debug(
            'getting %d first datapoints took %fs', len(result), elapsed)

    # Append all changes to it
    for ent_id, group in groupby(states, lambda state: state.entity_id):
        result[ent_id].extend(group)
    return result


def get_state(hass, utc_point_in_time, entity_id, run=None):
    """Return a state at a specific point in time."""
    states = list(get_states(hass, utc_point_in_time, (entity_id,), run))
    return states[0] if states else None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the history hooks."""
    filters = Filters()
    conf = config.get(DOMAIN, {})
    exclude = conf.get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
    include = conf.get(CONF_INCLUDE)
    if include:
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])
    use_include_order = conf.get(CONF_ORDER)

    hass.http.register_view(HistoryPeriodView(filters, use_include_order))
    yield from hass.components.frontend.async_register_built_in_panel(
        'history', 'history', 'mdi:poll-box')

    return True


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = '/api/history/period'
    name = 'api:history:view-period'
    extra_urls = ['/api/history/period/{datetime}']

    def __init__(self, filters, use_include_order):
        """Initialize the history period view."""
        self.filters = filters
        self.use_include_order = use_include_order

    @asyncio.coroutine
    def get(self, request, datetime=None):
        """Return history over a period of time."""
        timer_start = time.perf_counter()
        if datetime:
            datetime = dt_util.parse_datetime(datetime)

            if datetime is None:
                return self.json_message('Invalid datetime', HTTP_BAD_REQUEST)

        now = dt_util.utcnow()

        one_day = timedelta(days=1)
        if datetime:
            start_time = dt_util.as_utc(datetime)
        else:
            start_time = now - one_day

        if start_time > now:
            return self.json([])

        end_time = request.query.get('end_time')
        if end_time:
            end_time = dt_util.parse_datetime(end_time)
            if end_time:
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message('Invalid end_time', HTTP_BAD_REQUEST)
        else:
            end_time = start_time + one_day
        entity_ids = request.query.get('filter_entity_id')
        if entity_ids:
            entity_ids = entity_ids.lower().split(',')
        include_start_time_state = 'skip_initial_state' not in request.query

        hass = request.app['hass']

        result = yield from hass.async_add_job(
            get_significant_states, hass, start_time, end_time,
            entity_ids, self.filters, include_start_time_state)
        result = list(result.values())
        if _LOGGER.isEnabledFor(logging.DEBUG):
            elapsed = time.perf_counter() - timer_start
            _LOGGER.debug(
                'Extracted %d states in %fs', sum(map(len, result)), elapsed)

        # Optionally reorder the result to respect the ordering given
        # by any entities explicitly included in the configuration.

        if self.use_include_order:
            sorted_result = []
            for order_entity in self.filters.included_entities:
                for state_list in result:
                    if state_list[0].entity_id == order_entity:
                        sorted_result.append(state_list)
                        result.remove(state_list)
                        break
            sorted_result.extend(result)
            result = sorted_result

        response = yield from hass.async_add_job(self.json, result)
        return response


class Filters(object):
    """Container for the configured include and exclude filters."""

    def __init__(self):
        """Initialise the include and exclude filters."""
        self.excluded_entities = []
        self.excluded_domains = []
        self.included_entities = []
        self.included_domains = []

    def apply(self, query, entity_ids=None):
        """Apply the include/exclude filter on domains and entities on query.

        Following rules apply:
        * only the include section is configured - just query the specified
          entities or domains.
        * only the exclude section is configured - filter the specified
          entities and domains from all the entities in the system.
        * if include and exclude is defined - select the entities specified in
          the include and filter out the ones from the exclude list.
        """
        from homeassistant.components.recorder.models import States

        # specific entities requested - do not in/exclude anything
        if entity_ids is not None:
            return query.filter(States.entity_id.in_(entity_ids))
        query = query.filter(~States.domain.in_(IGNORE_DOMAINS))

        filter_query = None
        # filter if only excluded domain is configured
        if self.excluded_domains and not self.included_domains:
            filter_query = ~States.domain.in_(self.excluded_domains)
            if self.included_entities:
                filter_query &= States.entity_id.in_(self.included_entities)
        # filter if only included domain is configured
        elif not self.excluded_domains and self.included_domains:
            filter_query = States.domain.in_(self.included_domains)
            if self.included_entities:
                filter_query |= States.entity_id.in_(self.included_entities)
        # filter if included and excluded domain is configured
        elif self.excluded_domains and self.included_domains:
            filter_query = ~States.domain.in_(self.excluded_domains)
            if self.included_entities:
                filter_query &= (States.domain.in_(self.included_domains) |
                                 States.entity_id.in_(self.included_entities))
            else:
                filter_query &= (States.domain.in_(self.included_domains) & ~
                                 States.domain.in_(self.excluded_domains))
        # no domain filter just included entities
        elif not self.excluded_domains and not self.included_domains and \
                self.included_entities:
            filter_query = States.entity_id.in_(self.included_entities)
        if filter_query is not None:
            query = query.filter(filter_query)
        # finally apply excluded entities filter if configured
        if self.excluded_entities:
            query = query.filter(~States.entity_id.in_(self.excluded_entities))
        return query


def _is_significant(state):
    """Test if state is significant for history charts.

    Will only test for things that are not filtered out in SQL.
    """
    # scripts that are not cancellable will never change state
    return (state.domain != 'script' or
            state.attributes.get(script.ATTR_CAN_CANCEL))
