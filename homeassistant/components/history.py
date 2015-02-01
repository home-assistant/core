"""
homeassistant.components.history
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provide pre-made queries on top of the recorder component.
"""
import re

import homeassistant.components.recorder as recorder

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']


def last_5_states(entity_id):
    """ Return the last 5 states for entity_id. """
    query = """
        SELECT * FROM states WHERE entity_id=? AND
        last_changed=last_updated AND {}
        ORDER BY last_changed DESC LIMIT 0, 5
    """.format(recorder.limit_to_run())

    return recorder.query_states(query, (entity_id, ))


def setup(hass, config):
    """ Setup history hooks. """
    hass.http.register_path(
        'GET',
        re.compile(
            r'/api/history/(?P<entity_id>[a-zA-Z\._0-9]+)/recent_states'),
        _api_last_5_states)

    return True


# pylint: disable=invalid-name
def _api_last_5_states(handler, path_match, data):
    """ Return the last 5 states for an entity id as JSON. """
    entity_id = path_match.group('entity_id')

    handler.write_json(list(last_5_states(entity_id)))
