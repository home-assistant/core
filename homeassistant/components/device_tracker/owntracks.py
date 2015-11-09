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

DEPENDENCIES = ['mqtt']

LOCATION_TOPIC = 'owntracks/+/+'


def setup_scanner(hass, config, see):
    """ Set up a OwnTracksks tracker. """

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

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    return True
