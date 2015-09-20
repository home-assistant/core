"""
homeassistant.components.device_tracker.owntracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OwnTracks platform for the device tracker.

device_tracker:
  platform: owntracks
"""
import json

import homeassistant.components.mqtt as mqtt

DEPENDENCIES = ['mqtt']

LOCATION_TOPIC = 'owntracks/+/+'


def setup_scanner(hass, config, see):
    """ Set up a MQTT tracker. """

    def owntracks_location_update(topic, payload, qos):
        """ MQTT message received. """

        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typelocation

        parts = topic.split('/')
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            return
        if data.get('_type') != 'location':
            return
        dev_id = '{}_{}'.format(parts[1], parts[2])
        see(dev_id=dev_id, host_name=parts[1], gps=(data['lat'], data['lon']),
            gps_accuracy=data['acc'], battery=data['batt'])

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    return True
