"""Offer MQTT listening automation rules."""
import json

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import mqtt
from homeassistant.const import (CONF_PLATFORM, CONF_PAYLOAD)
import homeassistant.helpers.config_validation as cv

CONF_ENCODING = 'encoding'
CONF_TOPIC = 'topic'
DEFAULT_ENCODING = 'utf-8'

TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): mqtt.DOMAIN,
    vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
})


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    topic = config[CONF_TOPIC]
    payload = config.get(CONF_PAYLOAD)
    encoding = config[CONF_ENCODING] or None

    @callback
    def mqtt_automation_listener(mqttmsg):
        """Listen for MQTT messages."""
        if payload is None or payload == mqttmsg.payload:
            data = {
                'platform': 'mqtt',
                'topic': mqttmsg.topic,
                'payload': mqttmsg.payload,
                'qos': mqttmsg.qos,
            }

            try:
                data['payload_json'] = json.loads(mqttmsg.payload)
            except ValueError:
                pass

            hass.async_run_job(action, {
                'trigger': data
            })

    remove = await mqtt.async_subscribe(
        hass, topic, mqtt_automation_listener, encoding=encoding)
    return remove
