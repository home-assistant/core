"""
Offer MQTT listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#mqtt-trigger
"""
import asyncio
import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (CONF_PLATFORM, CONF_PAYLOAD)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

CONF_TOPIC = 'topic'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): mqtt.DOMAIN,
    vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_PAYLOAD): cv.string,
})


def async_trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    topic = config.get(CONF_TOPIC)
    payload = config.get(CONF_PAYLOAD)

    @asyncio.coroutine
    def mqtt_automation_listener(msg_topic, msg_payload, qos):
        """Listen for MQTT messages."""
        if payload is None or payload == msg_payload:
            hass.async_add_job(action, {
                'trigger': {
                    'platform': 'mqtt',
                    'topic': msg_topic,
                    'payload': msg_payload,
                    'qos': qos,
                }
            })

    return mqtt.async_subscribe(hass, topic, mqtt_automation_listener)
