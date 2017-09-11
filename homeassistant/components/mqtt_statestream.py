"""
Publish simple item state changes via MQTT.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt_statestream/
"""
import asyncio

import voluptuous as vol

from homeassistant.const import MATCH_ALL
from homeassistant.core import callback
from homeassistant.components.mqtt import valid_publish_topic
from homeassistant.helpers.event import async_track_state_change

CONF_BASE_TOPIC = 'base_topic'
DEPENDENCIES = ['mqtt']
DOMAIN = 'mqtt_statestream'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_BASE_TOPIC): valid_publish_topic
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the MQTT state feed."""
    conf = config.get(DOMAIN, {})
    base_topic = conf.get(CONF_BASE_TOPIC)
    if not base_topic.endswith('/'):
        base_topic = base_topic + '/'

    @callback
    def _state_publisher(entity_id, old_state, new_state):
        if new_state is None:
            return
        payload = new_state.state

        topic = base_topic + entity_id.replace('.', '/')
        hass.components.mqtt.async_publish(topic, payload, 1, True)

    async_track_state_change(hass, MATCH_ALL, _state_publisher)
    return True
