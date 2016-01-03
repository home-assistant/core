"""
homeassistant.components.device_tracker.owntracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
OwnTracks platform for the device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks/
"""
import json
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (STATE_HOME, STATE_NOT_HOME)

DEPENDENCIES = ['mqtt']

CONF_TRANSITION_EVENTS = 'use_events'
LOCATION_TOPIC = 'owntracks/+/+'
EVENT_TOPIC = 'owntracks/+/+/event'


def setup_scanner(hass, config, see):
    """ Set up an OwnTracks tracker. """

    def owntracks_location_update(topic, payload, qos):
        """ MQTT message received. """

        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typelocation
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            logging.getLogger(__name__).error(
                'Unable to parse payload as JSON: %s', payload)
            return

        if not isinstance(data, dict) or data.get('_type') != 'location':
            return

        parts = topic.split('/')
        kwargs = {
            'dev_id': '{}_{}'.format(parts[1], parts[2]),
            'host_name': parts[1],
            'gps': (data['lat'], data['lon']),
        }
        if 'acc' in data:
            kwargs['gps_accuracy'] = data['acc']
        if 'batt' in data:
            kwargs['battery'] = data['batt']

        see(**kwargs)

    def owntracks_event_update(topic, payload, qos):
        """ MQTT event (geofences) received. """

        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typetransition
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            logging.getLogger(__name__).error(
                'Unable to parse payload as JSON: %s', payload)
            return

        if not isinstance(data, dict) or data.get('_type') != 'transition':
            return

        # check if in "home" fence or other zone
        location = ''
        if data['event'] == 'enter':

            if data['desc'] == 'home':
                location = STATE_HOME
            else:
                location = data['desc']

        elif data['event'] == 'leave':
            location = STATE_NOT_HOME
        else:
            logging.getLogger(__name__).error(
                'Misformatted mqtt msgs, _type=transition, event=%s',
                data['event'])
            return

        parts = topic.split('/')
        kwargs = {
            'dev_id': '{}_{}'.format(parts[1], parts[2]),
            'host_name': parts[1],
            'gps': (data['lat'], data['lon']),
            'location_name': location,
        }
        if 'acc' in data:
            kwargs['gps_accuracy'] = data['acc']

        see(**kwargs)

    use_events = config.get(CONF_TRANSITION_EVENTS)

    if use_events:
        mqtt.subscribe(hass, EVENT_TOPIC, owntracks_event_update, 1)
    else:
        mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    return True
