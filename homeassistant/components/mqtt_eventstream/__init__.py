"""Connect two Home Assistant instances via MQTT."""

import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import valid_publish_topic, valid_subscribe_topic
from homeassistant.const import (
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    MATCH_ALL,
)
from homeassistant.core import EventOrigin, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_eventstream"
CONF_PUBLISH_TOPIC = "publish_topic"
CONF_SUBSCRIBE_TOPIC = "subscribe_topic"
CONF_PUBLISH_EVENTSTREAM_RECEIVED = "publish_eventstream_received"
CONF_IGNORE_EVENT = "ignore_event"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PUBLISH_TOPIC): valid_publish_topic,
                vol.Optional(CONF_SUBSCRIBE_TOPIC): valid_subscribe_topic,
                vol.Optional(
                    CONF_PUBLISH_EVENTSTREAM_RECEIVED, default=False
                ): cv.boolean,
                vol.Optional(CONF_IGNORE_EVENT, default=[]): cv.ensure_list,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

BLOCKED_EVENTS = [
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MQTT eventstream component."""
    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    conf = config.get(DOMAIN, {})
    pub_topic = conf.get(CONF_PUBLISH_TOPIC)
    sub_topic = conf.get(CONF_SUBSCRIBE_TOPIC)
    ignore_event = conf.get(CONF_IGNORE_EVENT)

    async def _event_publisher(event):
        """Handle events by publishing them on the MQTT queue."""
        if event.origin != EventOrigin.local:
            return

        # Events to ignore
        if event.event_type in ignore_event:
            return

        # Filter out the events that were triggered by publishing
        # to the MQTT topic, or you will end up in an infinite loop.
        if (
            event.event_type == EVENT_CALL_SERVICE
            and event.data.get("domain") == mqtt.DOMAIN
            and event.data.get("service") == mqtt.SERVICE_PUBLISH
            and event.data[ATTR_SERVICE_DATA].get("topic") == pub_topic
        ):
            return

        event_info = {"event_type": event.event_type, "event_data": event.data}
        msg = json.dumps(event_info, cls=JSONEncoder)
        await mqtt.async_publish(hass, pub_topic, msg)

    # Only listen for local events if you are going to publish them.
    if pub_topic:
        hass.bus.async_listen(MATCH_ALL, _event_publisher)

    # Process events from a remote server that are received on a queue.
    @callback
    def _event_receiver(msg):
        """Receive events published by and fire them on this hass instance."""
        event = json.loads(msg.payload)
        event_type = event.get("event_type")
        event_data = event.get("event_data")

        # Don't fire HOMEASSISTANT_* events on this instance
        if event_type in BLOCKED_EVENTS:
            return

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        # Copied over from the _handle_api_post_events_event method
        # of the api component.
        if event_type == EVENT_STATE_CHANGED and event_data:
            for key in ("old_state", "new_state"):
                state = State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        hass.bus.async_fire(
            event_type, event_data=event_data, origin=EventOrigin.remote
        )

    # Only subscribe if you specified a topic.
    if sub_topic:
        await mqtt.async_subscribe(hass, sub_topic, _event_receiver)

    return True
