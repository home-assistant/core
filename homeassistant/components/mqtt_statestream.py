"""
Publish simple item state changes via MQTT.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt_statestream/
"""
import asyncio

import voluptuous as vol

import homeassistant.loader as loader
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.components.mqtt import valid_publish_topic

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
    mqtt = loader.get_component('mqtt')
    conf = config.get(DOMAIN, {})
    base_topic = conf.get(CONF_BASE_TOPIC)
    if not base_topic.endswith('/'):
        base_topic = base_topic + '/'

    @callback
    def _event_publisher(event):
        """Handle state change events and publish them to MQTT."""
        if event.event_type == EVENT_STATE_CHANGED:
            try:
                new_state = event.data['new_state']
            except AttributeError:
                return

            try:
                payload = new_state.state
            except NameError:
                return

            topic = base_topic + new_state.entity_id.replace('.', '/')
            mqtt.async_publish(hass, topic, payload, 1, True)

    hass.bus.async_listen(EVENT_STATE_CHANGED, _event_publisher)

    hass.states.async_set('{domain}.initialized'.format(domain=DOMAIN), True)
    return True
