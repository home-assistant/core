"""
homeassistant.components.logbook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parses events and generates a human log.
"""
from datetime import timedelta
from itertools import groupby
import re

from homeassistant.core import State, DOMAIN as HA_DOMAIN
from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_HOME, STATE_ON, STATE_OFF,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, HTTP_BAD_REQUEST)
import homeassistant.util.dt as dt_util
import homeassistant.components.recorder as recorder
import homeassistant.components.sun as sun

DOMAIN = "logbook"
DEPENDENCIES = ['recorder', 'http']

URL_LOGBOOK = re.compile(r'/api/logbook(?:/(?P<date>\d{4}-\d{1,2}-\d{1,2})|)')

QUERY_EVENTS_BETWEEN = """
    SELECT * FROM events WHERE time_fired > ? AND time_fired < ?
"""

GROUP_BY_MINUTES = 15


def setup(hass, config):
    """ Listens for download events to download files. """
    hass.http.register_path('GET', URL_LOGBOOK, _handle_get_logbook)

    return True


def _handle_get_logbook(handler, path_match, data):
    """ Return logbook entries. """
    date_str = path_match.group('date')

    if date_str:
        start_date = dt_util.date_str_to_date(date_str)

        if start_date is None:
            handler.write_json_message("Error parsing JSON", HTTP_BAD_REQUEST)
            return

        start_day = dt_util.start_of_local_day(start_date)
    else:
        start_day = dt_util.start_of_local_day()

    end_day = start_day + timedelta(days=1)

    events = recorder.query_events(
        QUERY_EVENTS_BETWEEN,
        (dt_util.as_utc(start_day), dt_util.as_utc(end_day)))

    handler.write_json(humanify(events))


class Entry(object):
    """ A human readable version of the log. """

    # pylint: disable=too-many-arguments, too-few-public-methods

    def __init__(self, when=None, name=None, message=None, domain=None,
                 entity_id=None):
        self.when = when
        self.name = name
        self.message = message
        self.domain = domain
        self.entity_id = entity_id

    def as_dict(self):
        """ Convert Entry to a dict to be used within JSON. """
        return {
            'when': dt_util.datetime_to_str(self.when),
            'name': self.name,
            'message': self.message,
            'domain': self.domain,
            'entity_id': self.entity_id,
        }


def humanify(events):
    """
    Generator that converts a list of events into Entry objects.

    Will try to group events if possible:
     - if 2+ sensor updates in GROUP_BY_MINUTES, show last
     - if home assistant stop and start happen in same minute call it restarted
    """
    # pylint: disable=too-many-branches

    # Group events in batches of GROUP_BY_MINUTES
    for _, g_events in groupby(
            events,
            lambda event: event.time_fired.minute // GROUP_BY_MINUTES):

        events_batch = list(g_events)

        # Keep track of last sensor states
        last_sensor_event = {}

        # group HA start/stop events
        # Maps minute of event to 1: stop, 2: stop + start
        start_stop_events = {}

        # Process events
        for event in events_batch:
            if event.event_type == EVENT_STATE_CHANGED:
                entity_id = event.data['entity_id']

                if entity_id.startswith('sensor.'):
                    last_sensor_event[entity_id] = event

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if event.time_fired.minute in start_stop_events:
                    continue

                start_stop_events[event.time_fired.minute] = 1

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if event.time_fired.minute not in start_stop_events:
                    continue

                start_stop_events[event.time_fired.minute] = 2

        # Yield entries
        for event in events_batch:
            if event.event_type == EVENT_STATE_CHANGED:

                # Do not report on new entities
                if 'old_state' not in event.data:
                    continue

                to_state = State.from_dict(event.data.get('new_state'))

                # if last_changed == last_updated only attributes have changed
                # we do not report on that yet.
                if not to_state or \
                   to_state.last_changed != to_state.last_updated:
                    continue

                domain = to_state.domain

                # Skip all but the last sensor state
                if domain == 'sensor' and \
                   event != last_sensor_event[to_state.entity_id]:
                    continue

                yield Entry(
                    event.time_fired,
                    name=to_state.name,
                    message=_entry_message_from_state(domain, to_state),
                    domain=domain,
                    entity_id=to_state.entity_id)

            elif event.event_type == EVENT_HOMEASSISTANT_START:
                if start_stop_events.get(event.time_fired.minute) == 2:
                    continue

                yield Entry(
                    event.time_fired, "Home Assistant", "started",
                    domain=HA_DOMAIN)

            elif event.event_type == EVENT_HOMEASSISTANT_STOP:
                if start_stop_events.get(event.time_fired.minute) == 2:
                    action = "restarted"
                else:
                    action = "stopped"

                yield Entry(
                    event.time_fired, "Home Assistant", action,
                    domain=HA_DOMAIN)


def _entry_message_from_state(domain, state):
    """ Convert a state to a message for the logbook. """
    # We pass domain in so we don't have to split entity_id again

    if domain == 'device_tracker':
        return '{} home'.format(
            'arrived' if state.state == STATE_HOME else 'left')

    elif domain == 'sun':
        if state.state == sun.STATE_ABOVE_HORIZON:
            return 'has risen'
        else:
            return 'has set'

    elif state.state == STATE_ON:
        # Future: combine groups and its entity entries ?
        return "turned on"

    elif state.state == STATE_OFF:
        return "turned off"

    return "changed to {}".format(state.state)
