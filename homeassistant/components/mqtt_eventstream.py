"""
Connect two Home Assistant instances via MQTT.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt_eventstream/
"""
import asyncio
import json

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.loader as loader
from homeassistant.components.mqtt import (
    valid_publish_topic, valid_subscribe_topic)
from homeassistant.const import (
    ATTR_SERVICE_DATA, EVENT_CALL_SERVICE, EVENT_SERVICE_EXECUTED,
    EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL)
from homeassistant.core import EventOrigin, State
import homeassistant.helpers.config_validation as cv
from homeassistant.remote import JSONEncoder

DOMAIN = 'mqtt_eventstream'
DEPENDENCIES = ['mqtt']

CONF_PUBLISH_TOPIC = 'publish_topic'
CONF_SUBSCRIBE_TOPIC = 'subscribe_topic'
CONF_PUBLISH_EVENTSTREAM_RECEIVED = 'publish_eventstream_received'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PUBLISH_TOPIC): valid_publish_topic,
        vol.Optional(CONF_SUBSCRIBE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_PUBLISH_EVENTSTREAM_RECEIVED, default=False):
            cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the MQTT eventstream component."""
    mqtt = loader.get_component('mqtt')
    conf = config.get(DOMAIN, {})
    pub_topic = conf.get(CONF_PUBLISH_TOPIC)
    sub_topic = conf.get(CONF_SUBSCRIBE_TOPIC)

    @callback
    def _event_publisher(event):
        """Handle events by publishing them on the MQTT queue."""
        if event.origin != EventOrigin.local:
            return
        if event.event_type == EVENT_TIME_CHANGED:
            return

        # Filter out the events that were triggered by publishing
        # to the MQTT topic, or you will end up in an infinite loop.
        if event.event_type == EVENT_CALL_SERVICE:
            if (
                    event.data.get('domain') == mqtt.DOMAIN and
                    event.data.get('service') == mqtt.SERVICE_PUBLISH and
                    event.data[ATTR_SERVICE_DATA].get('topic') == pub_topic
            ):
                return

        # Filter out all the "event service executed" events because they
        # are only used internally by core as callbacks for blocking
        # during the interval while a service is being executed.
        # They will serve no purpose to the external system,
        # and thus are unnecessary traffic.
        # And at any rate it would cause an infinite loop to publish them
        # because publishing to an MQTT topic itself triggers one.
        if event.event_type == EVENT_SERVICE_EXECUTED:
            return

        event_info = {'event_type': event.event_type, 'event_data': event.data}
        msg = json.dumps(event_info, cls=JSONEncoder)
        mqtt.async_publish(hass, pub_topic, msg)

    # Only listen for local events if you are going to publish them.
    if pub_topic:
        hass.bus.async_listen(MATCH_ALL, _event_publisher)

    # Process events from a remote server that are received on a queue.
    @callback
    def _event_receiver(topic, payload, qos):
        """Receive events published by and fire them on this hass instance."""
        event = json.loads(payload)
        event_type = event.get('event_type')
        event_data = event.get('event_data')

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        # Copied over from the _handle_api_post_events_event method
        # of the api component.
        if event_type == EVENT_STATE_CHANGED and event_data:
            for key in ('old_state', 'new_state'):
                state = State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        hass.bus.async_fire(
            event_type,
            event_data=event_data,
            origin=EventOrigin.remote
        )

    # Only subscribe if you specified a topic.
    if sub_topic:
        yield from mqtt.async_subscribe(hass, sub_topic, _event_receiver)

    hass.states.async_set('{domain}.initialized'.format(domain=DOMAIN), True)
    return True
