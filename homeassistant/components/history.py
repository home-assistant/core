"""
homeassistant.components.history
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provide pre-made queries on top of the recorder component.
"""
import re
from datetime import timedelta
from itertools import groupby
from collections import defaultdict

import homeassistant.util.dt as date_util
import homeassistant.components.recorder as recorder

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']


def last_5_states(entity_id):
    """ Return the last 5 states for entity_id. """
    entity_id = entity_id.lower()

    query = """
        SELECT * FROM states WHERE entity_id=? AND
        last_changed=last_updated
        ORDER BY last_changed DESC LIMIT 0, 5
    """

    return recorder.query_states(query, (entity_id, ))


def state_changes_during_period(start_time, end_time=None, entity_id=None):
    """
    Return states changes during UTC period start_time - end_time.
    """
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

    result = defaultdict(list)

    entity_ids = [entity_id] if entity_id is not None else None

    # Get the states at the start time
    for state in get_states(start_time, entity_ids):
        state.last_changed = start_time
        result[state.entity_id].append(state)

    # Append all changes to it
    for entity_id, group in groupby(states, lambda state: state.entity_id):
        result[entity_id].extend(group)

    return result


def get_states(utc_point_in_time, entity_ids=None, run=None):
    """ Returns the states at a specific point in time. """
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


def get_state(utc_point_in_time, entity_id, run=None):
    """ Return a state at a specific point in time. """
    states = get_states(utc_point_in_time, (entity_id,), run)

    return states[0] if states else None


# pylint: disable=unused-argument
def setup(hass, config):
    """ Setup history hooks. """
    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/history/entity/(?P<entity_id>[a-zA-Z\._0-9]+)/'
            r'recent_states'),
        _api_last_5_states)

    hass.http.register_path(
        'GET', re.compile(r'/api/history/period'), _api_history_period)

    return True


# pylint: disable=unused-argument
# pylint: disable=invalid-name
def _api_last_5_states(handler, path_match, data):
    """ Return the last 5 states for an entity id as JSON. """
    entity_id = path_match.group('entity_id')

    handler.write_json(last_5_states(entity_id))


def _api_history_period(handler, path_match, data):
    """ Return history over a period of time. """
    # 1 day for now..
    start_time = date_util.utcnow() - timedelta(seconds=86400)

    entity_id = data.get('filter_entity_id')

    handler.write_json(
        state_changes_during_period(start_time, entity_id=entity_id).values())
