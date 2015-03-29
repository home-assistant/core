"""
homeassistant.components.logbook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parses events and generates a human log
"""
from datetime import datetime

from homeassistant import State, DOMAIN as HA_DOMAIN
from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_HOME, STATE_ON, STATE_OFF,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.util as util
import homeassistant.components.recorder as recorder
import homeassistant.components.sun as sun

DOMAIN = "logbook"
DEPENDENCIES = ['recorder', 'http']

URL_LOGBOOK = '/api/logbook'

QUERY_EVENTS_AFTER = "SELECT * FROM events WHERE time_fired > ?"
QUERY_EVENTS_BETWEEN = """
    SELECT * FROM events WHERE time_fired > ? AND time_fired < ?
    ORDER BY time_fired
"""


def setup(hass, config):
    """ Listens for download events to download files. """
    hass.http.register_path('GET', URL_LOGBOOK, _handle_get_logbook)

    return True


def _handle_get_logbook(handler, path_match, data):
    """ Return logbook entries. """
    start_today = datetime.now().date()
    import time
    print(time.mktime(start_today.timetuple()))
    handler.write_json(humanify(
        recorder.query_events(QUERY_EVENTS_AFTER, (start_today,))))


class Entry(object):
    """ A human readable version of the log. """

    # pylint: disable=too-many-arguments

    def __init__(self, when=None, name=None, message=None, domain=None,
                 entity_id=None):
        self.when = when
        self.name = name
        self.message = message
        self.domain = domain
        self.entity_id = entity_id

    @property
    def is_valid(self):
        """ Returns if this entry contains all the needed fields. """
        return self.when and self.name and self.message

    def as_dict(self):
        """ Convert Entry to a dict to be used within JSON. """
        return {
            'when': util.datetime_to_str(self.when),
            'name': self.name,
            'message': self.message,
            'domain': self.domain,
            'entity_id': self.entity_id,
        }


def humanify(events):
    """ Generator that converts a list of events into Entry objects. """
    # pylint: disable=too-many-branches
    for event in events:
        if event.event_type == EVENT_STATE_CHANGED:

            # Do not report on new entities
            if 'old_state' not in event.data:
                continue

            to_state = State.from_dict(event.data.get('new_state'))

            if not to_state:
                continue

            domain = to_state.domain

            entry = Entry(
                event.time_fired, domain=domain,
                name=to_state.name, entity_id=to_state.entity_id)

            if domain == 'device_tracker':
                entry.message = '{} home'.format(
                    'arrived' if to_state.state == STATE_HOME else 'left')

            elif domain == 'sun':
                if to_state.state == sun.STATE_ABOVE_HORIZON:
                    entry.message = 'has risen'
                else:
                    entry.message = 'has set'

            elif to_state.state == STATE_ON:
                # Future: combine groups and its entity entries ?
                entry.message = "turned on"

            elif to_state.state == STATE_OFF:
                entry.message = "turned off"

            else:
                entry.message = "changed to {}".format(to_state.state)

            if entry.is_valid:
                yield entry

        elif event.event_type == EVENT_HOMEASSISTANT_START:
            # Future: look for sequence stop/start and rewrite as restarted
            yield Entry(
                event.time_fired, "Home Assistant", "started",
                domain=HA_DOMAIN)

        elif event.event_type == EVENT_HOMEASSISTANT_STOP:
            yield Entry(
                event.time_fired, "Home Assistant", "stopped",
                domain=HA_DOMAIN)
