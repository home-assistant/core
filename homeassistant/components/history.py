"""
homeassistant.components.history
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provide pre-made queries on top of the recorder component.
"""
import re
from datetime import datetime, timedelta
from itertools import groupby

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
    Return states changes during period start_time - end_time.
    Currently does _not_ include how the states where at exactly start_time.
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

    return [list(group) for _, group in
            groupby(states, lambda state: state.entity_id)]


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


# pylint: disable=invalid-name
def _api_last_5_states(handler, path_match, data):
    """ Return the last 5 states for an entity id as JSON. """
    entity_id = path_match.group('entity_id')

    handler.write_json(list(last_5_states(entity_id)))


def _api_history_period(handler, path_match, data):
    """ Return history over a period of time. """
    # 1 day for now..
    start_time = datetime.now() - timedelta(seconds=86400)

    entity_id = data.get('filter_entity_id')

    handler.write_json(
        state_changes_during_period(start_time, entity_id=entity_id))
