import re

import homeassistant.components.recorder as recorder

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']


def last_5_states(entity_id):
    """ Return the last 5 states for entity_id. """
    return recorder.query_states(
        "SELECT * FROM states WHERE entity_id=? AND "
        "last_changed=last_updated "
        "ORDER BY last_changed DESC LIMIT 0, 5", (entity_id, ))


def last_5_events():
    """ Return the last 5 events (dev method). """
    return recorder.query_events(
        "SELECT * FROM events ORDER BY created DESC LIMIT 0, 5")


def states_history(point_in_time):
    """ Return states at a specific point in time. """
    # Find homeassistant.start before point_in_time
    # Find last state for each entity after homeassistant.start
    # Ignore all states where state == ''
    pass


def setup(hass, config):
    """ Setup history hooks. """
    hass.http.register_path(
        'GET',
        re.compile('/api/component/recorder/(?P<entity_id>[a-zA-Z\._0-9]+)/last_5_states'),
        _api_last_5_states),
    hass.http.register_path(
        'GET',
        re.compile('/api/component/recorder/last_5_events'),
        _api_last_5_events),


# pylint: disable=invalid-name
def _api_last_5_states(handler, path_match, data):
    entity_id = path_match.group('entity_id')

    handler.write_json(list(last_5_states(entity_id)))


# pylint: disable=invalid-name
def _api_last_5_events(handler, path_match, data):
    handler.write_json(list(last_5_events))
