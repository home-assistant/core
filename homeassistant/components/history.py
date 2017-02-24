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
from homeassistant.components.frontend import register_built_in_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_HIDDEN

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: recorder.FILTER_SCHEMA,
}, extra=vol.ALLOW_EXTRA)

SIGNIFICANT_DOMAINS = ('thermostat', 'climate')
IGNORE_DOMAINS = ('zone', 'scene',)


def last_recorder_run():
    """Retireve the last closed recorder run from the DB."""
    recorder.get_instance()
    rec_runs = recorder.get_model('RecorderRuns')
    with recorder.session_scope() as session:
        res = recorder.query(rec_runs).order_by(rec_runs.end.desc()).first()
        if res is None:
            return None
        session.expunge(res)
        return res


def get_significant_states(start_time, end_time=None, entity_id=None,
                           filters=None):
    """
    Return states changes during UTC period start_time - end_time.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    entity_ids = (entity_id.lower(), ) if entity_id is not None else None
    states = recorder.get_model('States')
    query = recorder.query(states).filter(
        (states.domain.in_(SIGNIFICANT_DOMAINS) |
         (states.last_changed == states.last_updated)) &
        (states.last_updated > start_time))
    if filters:
        query = filters.apply(query, entity_ids)

    if end_time is not None:
        query = query.filter(states.last_updated < end_time)

    states = (
        state for state in recorder.execute(
            query.order_by(states.entity_id, states.last_updated))
        if (_is_significant(state) and
            not state.attributes.get(ATTR_HIDDEN, False)))

    return states_to_json(states, start_time, entity_id, filters)


def state_changes_during_period(start_time, end_time=None, entity_id=None):
    """Return states changes during UTC period start_time - end_time."""
    states = recorder.get_model('States')
    query = recorder.query(states).filter(
        (states.last_changed == states.last_updated) &
        (states.last_changed > start_time))

    if end_time is not None:
        query = query.filter(states.last_updated < end_time)

    if entity_id is not None:
        query = query.filter_by(entity_id=entity_id.lower())

    states = recorder.execute(
        query.order_by(states.entity_id, states.last_updated))

    return states_to_json(states, start_time, entity_id)


def get_states(utc_point_in_time, entity_ids=None, run=None, filters=None):
    """Return the states at a specific point in time."""
    if run is None:
        run = recorder.run_information(utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    from sqlalchemy import and_, func

    states = recorder.get_model('States')
    most_recent_state_ids = recorder.query(
        func.max(states.state_id).label('max_state_id')
    ).filter(
        (states.created >= run.start) &
        (states.created < utc_point_in_time) &
        (~states.domain.in_(IGNORE_DOMAINS)))
    if filters:
        most_recent_state_ids = filters.apply(most_recent_state_ids,
                                              entity_ids)

    most_recent_state_ids = most_recent_state_ids.group_by(
        states.entity_id).subquery()

    query = recorder.query(states).join(most_recent_state_ids, and_(
        states.state_id == most_recent_state_ids.c.max_state_id))

    for state in recorder.execute(query):
        if not state.attributes.get(ATTR_HIDDEN, False):
            yield state


def states_to_json(states, start_time, entity_id, filters=None):
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    result = defaultdict(list)

    entity_ids = [entity_id] if entity_id is not None else None

    # Get the states at the start time
    for state in get_states(start_time, entity_ids, filters=filters):
        state.last_changed = start_time
        state.last_updated = start_time
        result[state.entity_id].append(state)

    # Append all changes to it
    for entity_id, group in groupby(states, lambda state: state.entity_id):
        result[entity_id].extend(group)
    return result


def get_state(utc_point_in_time, entity_id, run=None):
    """Return a state at a specific point in time."""
    states = list(get_states(utc_point_in_time, (entity_id,), run))
    return states[0] if states else None


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the history hooks."""
    filters = Filters()
    exclude = config[DOMAIN].get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude[CONF_ENTITIES]
        filters.excluded_domains = exclude[CONF_DOMAINS]
    include = config[DOMAIN].get(CONF_INCLUDE)
    if include:
        filters.included_entities = include[CONF_ENTITIES]
        filters.included_domains = include[CONF_DOMAINS]

    recorder.get_instance()
    hass.http.register_view(HistoryPeriodView(filters))
    register_built_in_panel(hass, 'history', 'History', 'mdi:poll-box')

    return True


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = '/api/history/period'
    name = 'api:history:view-period'
    extra_urls = ['/api/history/period/{datetime}']

    def __init__(self, filters):
        """Initilalize the history period view."""
        self.filters = filters

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

        end_time = request.GET.get('end_time')
        if end_time:
            end_time = dt_util.as_utc(
                dt_util.parse_datetime(end_time))
            if end_time is None:
                return self.json_message('Invalid end_time', HTTP_BAD_REQUEST)
        else:
            end_time = start_time + one_day
        entity_id = request.GET.get('filter_entity_id')

        result = yield from request.app['hass'].loop.run_in_executor(
            None, get_significant_states, start_time, end_time, entity_id,
            self.filters)
        result = result.values()
        if _LOGGER.isEnabledFor(logging.DEBUG):
            elapsed = time.perf_counter() - timer_start
            _LOGGER.debug(
                'Extracted %d states in %fs', sum(map(len, result)), elapsed)
        return self.json(result)


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
        states = recorder.get_model('States')
        # specific entities requested - do not in/exclude anything
        if entity_ids is not None:
            return query.filter(states.entity_id.in_(entity_ids))
        query = query.filter(~states.domain.in_(IGNORE_DOMAINS))

        filter_query = None
        # filter if only excluded domain is configured
        if self.excluded_domains and not self.included_domains:
            filter_query = ~states.domain.in_(self.excluded_domains)
            if self.included_entities:
                filter_query &= states.entity_id.in_(self.included_entities)
        # filter if only included domain is configured
        elif not self.excluded_domains and self.included_domains:
            filter_query = states.domain.in_(self.included_domains)
            if self.included_entities:
                filter_query |= states.entity_id.in_(self.included_entities)
        # filter if included and excluded domain is configured
        elif self.excluded_domains and self.included_domains:
            filter_query = ~states.domain.in_(self.excluded_domains)
            if self.included_entities:
                filter_query &= (states.domain.in_(self.included_domains) |
                                 states.entity_id.in_(self.included_entities))
            else:
                filter_query &= (states.domain.in_(self.included_domains) & ~
                                 states.domain.in_(self.excluded_domains))
        # no domain filter just included entities
        elif not self.excluded_domains and not self.included_domains and \
                self.included_entities:
            filter_query = states.entity_id.in_(self.included_entities)
        if filter_query is not None:
            query = query.filter(filter_query)
        # finally apply excluded entities filter if configured
        if self.excluded_entities:
            query = query.filter(~states.entity_id.in_(self.excluded_entities))
        return query


def _is_significant(state):
    """Test if state is significant for history charts.

    Will only test for things that are not filtered out in SQL.
    """
    # scripts that are not cancellable will never change state
    return (state.domain != 'script' or
            state.attributes.get(script.ATTR_CAN_CANCEL))
