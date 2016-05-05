"""
Provide pre-made queries on top of the recorder component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/history/
"""
import re
from collections import defaultdict
from datetime import timedelta
from itertools import groupby

from homeassistant.components import recorder, script
import homeassistant.util.dt as dt_util
from homeassistant.const import HTTP_BAD_REQUEST

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']

SIGNIFICANT_DOMAINS = ('thermostat',)
IGNORE_DOMAINS = ('zone', 'scene',)

URL_HISTORY_PERIOD = re.compile(
    r'/api/history/period(?:/(?P<date>\d{4}-\d{1,2}-\d{1,2})|)')


def last_5_states(entity_id):
    """Return the last 5 states for entity_id."""
    entity_id = entity_id.lower()

    query = """
        SELECT * FROM states WHERE entity_id=? AND
        last_changed=last_updated
        ORDER BY state_id DESC LIMIT 0, 5
    """

    return recorder.query_states(query, (entity_id, ))


def get_significant_states(start_time, end_time=None, entity_id=None):
    """
    Return states changes during UTC period start_time - end_time.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    where = """
        (domain IN ({}) OR last_changed=last_updated)
        AND domain NOT IN ({}) AND last_updated > ?
    """.format(",".join("'%s'" % x for x in SIGNIFICANT_DOMAINS),
               ",".join("'%s'" % x for x in IGNORE_DOMAINS))

    data = [start_time]

    if end_time is not None:
        where += "AND last_updated < ? "
        data.append(end_time)

    if entity_id is not None:
        where += "AND entity_id = ? "
        data.append(entity_id.lower())

    query = ("SELECT * FROM states WHERE {} "
             "ORDER BY entity_id, last_updated ASC").format(where)

    states = (state for state in recorder.query_states(query, data)
              if _is_significant(state))

    return states_to_json(states, start_time, entity_id)


def state_changes_during_period(start_time, end_time=None, entity_id=None):
    """Return states changes during UTC period start_time - end_time."""
    where = "last_changed=last_updated AND last_changed > ? "
    data = [start_time]

    if end_time is not None:
        where += "AND last_changed < ? "
        data.append(end_time)

    if entity_id is not None:
        where += "AND entity_id = ? "
        data.append(entity_id.lower())

    query = ("SELECT * FROM states WHERE {} "
             "ORDER BY entity_id, last_changed ASC").format(where)

    states = recorder.query_states(query, data)

    return states_to_json(states, start_time, entity_id)


def get_states(utc_point_in_time, entity_ids=None, run=None):
    """Return the states at a specific point in time."""
    if run is None:
        run = recorder.run_information(utc_point_in_time)

        # History did not run before utc_point_in_time
        if run is None:
            return []

    where = run.where_after_start_run + "AND created < ? "
    where_data = [utc_point_in_time]

    if entity_ids is not None:
        where += "AND entity_id IN ({}) ".format(
            ",".join(['?'] * len(entity_ids)))
        where_data.extend(entity_ids)

    query = """
        SELECT * FROM states
        INNER JOIN (
            SELECT max(state_id) AS max_state_id
            FROM states WHERE {}
            GROUP BY entity_id)
        WHERE state_id = max_state_id
    """.format(where)

    return recorder.query_states(query, where_data)


def states_to_json(states, start_time, entity_id):
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
    for state in get_states(start_time, entity_ids):
        state.last_changed = start_time
        state.last_updated = start_time
        result[state.entity_id].append(state)

    # Append all changes to it
    for entity_id, group in groupby(states, lambda state: state.entity_id):
        result[entity_id].extend(group)
    return result


def get_state(utc_point_in_time, entity_id, run=None):
    """Return a state at a specific point in time."""
    states = get_states(utc_point_in_time, (entity_id,), run)

    return states[0] if states else None


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the history hooks."""
    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/history/entity/(?P<entity_id>[a-zA-Z\._0-9]+)/'
            r'recent_states'),
        _api_last_5_states)

    hass.http.register_path('GET', URL_HISTORY_PERIOD, _api_history_period)

    return True


# pylint: disable=unused-argument
# pylint: disable=invalid-name
def _api_last_5_states(handler, path_match, data):
    """Return the last 5 states for an entity id as JSON."""
    entity_id = path_match.group('entity_id')

    handler.write_json(last_5_states(entity_id))


def _api_history_period(handler, path_match, data):
    """Return history over a period of time."""
    date_str = path_match.group('date')
    one_day = timedelta(seconds=86400)

    if date_str:
        start_date = dt_util.parse_date(date_str)

        if start_date is None:
            handler.write_json_message("Error parsing JSON", HTTP_BAD_REQUEST)
            return

        start_time = dt_util.as_utc(dt_util.start_of_local_day(start_date))
    else:
        start_time = dt_util.utcnow() - one_day

    end_time = start_time + one_day

    entity_id = data.get('filter_entity_id')

    handler.write_json(
        get_significant_states(start_time, end_time, entity_id).values())


def _is_significant(state):
    """Test if state is significant for history charts.

    Will only test for things that are not filtered out in SQL.
    """
    # scripts that are not cancellable will never change state
    return (state.domain != 'script' or
            state.attributes.get(script.ATTR_CAN_CANCEL))
