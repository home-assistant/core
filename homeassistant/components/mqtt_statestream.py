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
import homeassistant.helpers.config_validation as cv

CONF_BASE_TOPIC = 'base_topic'
CONF_PUBLISH_ATTRIBUTES = 'publish_attributes'
CONF_PUBLISH_TIMESTAMPS = 'publish_timestamps'
DEPENDENCIES = ['mqtt']
DOMAIN = 'mqtt_statestream'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_BASE_TOPIC): valid_publish_topic,
        vol.Optional(CONF_PUBLISH_ATTRIBUTES, default=False): cv.boolean,
        vol.Optional(CONF_PUBLISH_TIMESTAMPS, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the MQTT state feed."""
    conf = config.get(DOMAIN, {})
    base_topic = conf.get(CONF_BASE_TOPIC)
    publish_attributes = conf.get(CONF_PUBLISH_ATTRIBUTES)
    publish_timestamps = conf.get(CONF_PUBLISH_TIMESTAMPS)
    if not base_topic.endswith('/'):
        base_topic = base_topic + '/'

    @callback
    def _state_publisher(entity_id, old_state, new_state):
        if new_state is None:
            return
        payload = new_state.state

        mybase = base_topic + entity_id.replace('.', '/') + '/'
        hass.components.mqtt.async_publish(mybase + 'state', payload, 1, True)

        if publish_timestamps:
            if new_state.last_updated:
                hass.components.mqtt.async_publish(
                    mybase + 'last_updated',
                    new_state.last_updated.isoformat(),
                    1,
                    True)
            if new_state.last_changed:
                hass.components.mqtt.async_publish(
                    mybase + 'last_changed',
                    new_state.last_changed.isoformat(),
                    1,
                    True)

        if publish_attributes:
            for key, val in new_state.attributes.items():
                if val:
                    hass.components.mqtt.async_publish(mybase + key,
                                                       val, 1, True)

    async_track_state_change(hass, MATCH_ALL, _state_publisher)
    return True
