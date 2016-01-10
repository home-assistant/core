"""
homeassistant.components.mqtt_eventstream
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connect two Home Assistant instances via mqtt.

Configuration:

To use the mqtt_eventstream component you will need to add the following to
your configuration.yaml file.

If you do not specify a publish_topic you will not forward events to the queue.
If you do not specify a subscribe_topic then you will not receive events from
the remote server.

mqtt_eventstream:
  publish_topic: MyServerName
  subscribe_topic: OtherHaServerName
"""
import json
from homeassistant.core import EventOrigin, State
from homeassistant.const import (
    MATCH_ALL,
    EVENT_TIME_CHANGED,
    EVENT_CALL_SERVICE,
    EVENT_SERVICE_EXECUTED,
    EVENT_STATE_CHANGED,
)

import homeassistant.loader as loader
from homeassistant.remote import JSONEncoder

# The domain of your component. Should be equal to the name of your component
DOMAIN = "mqtt_eventstream"

# List of component names (string) your component depends upon
DEPENDENCIES = ['mqtt']


def setup(hass, config):
    """ Setup our mqtt_eventstream component. """
    def _event_handler(event):
        """ Handle events by publishing them on the mqtt queue. """
        if event.origin != EventOrigin.local:
            return
        if event.event_type in (
            EVENT_TIME_CHANGED,
            EVENT_CALL_SERVICE,
            EVENT_SERVICE_EXECUTED
        ):
            return
        event = {'event_type': event.event_type, 'event_data': event.data}
        msg = json.dumps(event, cls=JSONEncoder)
        mqtt.publish(hass, pub_topic, msg)

    mqtt = loader.get_component('mqtt')
    pub_topic = config[DOMAIN].get('publish_topic', None)
    sub_topic = config[DOMAIN].get('subscribe_topic', None)

    # Only listen for local events if you are going to publish them
    if (pub_topic):
        hass.bus.listen(MATCH_ALL, _event_handler)

    # Process events from a remote server that are received on a queue
    def _event_receiver(topic, payload, qos):
        """
        A new MQTT message, published by the other HA instance,
        has been received.
        """
        # TODO error handling
        event = json.loads(payload)
        event_type = event.get('event_type')
        event_data = event.get('event_data')

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        if event_type == EVENT_STATE_CHANGED and event_data:
            for key in ('old_state', 'new_state'):
                state = State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        hass.bus.fire(
            event_type,
            event_data=event_data,
            origin=EventOrigin.remote
        )

    # Only subscribe if you specified a topic
    if (sub_topic):
        mqtt.subscribe(hass, sub_topic, _event_receiver)

    hass.states.set('{domain}.initialized'.format(domain=DOMAIN), True)
    # return boolean to indicate that initialization was successful
    return True
