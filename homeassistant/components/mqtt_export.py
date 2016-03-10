"""
MQTT publisher for all Home Assistant states.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt_export/
"""
import json

import homeassistant.loader as loader
from homeassistant.const import (STATE_UNKNOWN, EVENT_STATE_CHANGED)
from homeassistant.remote import JSONEncoder

DOMAIN = "mqtt_export"
DEPENDENCIES = ['mqtt']

DEFAULT_TOPIC = 'home-assistant/states'
PAYLOAD = None


def setup(hass, config):
    """Setup the MQTT export component."""
    mqtt = loader.get_component('mqtt')
    pub_topic = config[DOMAIN].get('publish_topic', DEFAULT_TOPIC)

    global PAYLOAD
    PAYLOAD = dict(states=None, details=None)

    # Add the configuration
    PAYLOAD['details'] = hass.config.as_dict()

    def mqtt_event_listener(event):
        """Listen for new messages on the bus and send data to MQTT."""
        state = event.data.get('new_state')
        if state is None or state.state in (STATE_UNKNOWN, ''):
            return None

        PAYLOAD['states'] = hass.states.all()

        payload = json.dumps(PAYLOAD, cls=JSONEncoder)
        mqtt.publish(hass, pub_topic, payload)

    hass.bus.listen(EVENT_STATE_CHANGED, mqtt_event_listener)

    return True
