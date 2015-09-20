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
        parts = topic.split('/')
        data = json.loads(payload)
        dev_id = '{}_{}'.format(parts[1], parts[2])
        see(dev_id=dev_id, host_name=parts[1], gps=[data['lat'], data['lon']])

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    return True
