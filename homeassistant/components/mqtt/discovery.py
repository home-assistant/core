"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import json
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.mqtt import DOMAIN

_LOGGER = logging.getLogger(__name__)


def start(hass, discovery_config):
    """Initialization of MQTT Discovery."""
    if discovery_config is None:
        _LOGGER.warning("Can't setup MQTT discovery")
        return False

    def device_message_received(topic, payload, qos):
        """Process the received message."""
        parts = topic.split('/')
        entity_id = '{}.{}_{}'.format(parts[1], DOMAIN, parts[2])

        try:
            data = json.loads(str(payload))
        except ValueError:
            _LOGGER.warning("Payload for %s is not valid JSON", entity_id)

        try:
            new_state = data.get('state')
        except AttributeError:
            pass

        attributes = data.get('attributes')
        force_update = data.get('force_update', False)
        attributes['force_update'] = force_update
        attributes['topic'] = topic
        attributes['qos'] = qos

        is_new_state = hass.states.get(entity_id) is None

        hass.states.set(entity_id, new_state, attributes, force_update)

        if is_new_state:
            mqtt.publish(hass, '{}/{}'.format(topic, 'state'), qos)

    mqtt.subscribe(hass, discovery_config, device_message_received, 0)

    return True
