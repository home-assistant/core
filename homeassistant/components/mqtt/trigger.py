"""Offer MQTT listening automation rules."""
import json

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.const import CONF_PAYLOAD, CONF_PLATFORM
from homeassistant.core import HassJob, callback
import homeassistant.helpers.config_validation as cv

# mypy: allow-untyped-defs

CONF_ENCODING = "encoding"
CONF_QOS = "qos"
CONF_TOPIC = "topic"
DEFAULT_ENCODING = "utf-8"
DEFAULT_QOS = 0

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): mqtt.DOMAIN,
        vol.Required(CONF_TOPIC): mqtt.util.valid_subscribe_topic,
        vol.Optional(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
            vol.Coerce(int), vol.In([0, 1, 2])
        ),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    topic = config[CONF_TOPIC]
    payload = config.get(CONF_PAYLOAD)
    encoding = config[CONF_ENCODING] or None
    qos = config[CONF_QOS]
    job = HassJob(action)

    @callback
    def mqtt_automation_listener(mqttmsg):
        """Listen for MQTT messages."""
        if payload is None or payload == mqttmsg.payload:
            data = {
                "platform": "mqtt",
                "topic": mqttmsg.topic,
                "payload": mqttmsg.payload,
                "qos": mqttmsg.qos,
                "description": f"mqtt topic {mqttmsg.topic}",
            }

            try:
                data["payload_json"] = json.loads(mqttmsg.payload)
            except ValueError:
                pass

            hass.async_run_hass_job(job, {"trigger": data})

    remove = await mqtt.async_subscribe(
        hass, topic, mqtt_automation_listener, encoding=encoding, qos=qos
    )
    return remove
