"""Offer MQTT listening automation rules."""
from contextlib import suppress
import logging

import voluptuous as vol

from homeassistant.const import CONF_PAYLOAD, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.json import json_loads
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .. import mqtt
from .const import CONF_ENCODING, CONF_QOS, CONF_TOPIC, DEFAULT_ENCODING, DEFAULT_QOS

# mypy: allow-untyped-defs


TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): mqtt.DOMAIN,
        vol.Required(CONF_TOPIC): mqtt.util.valid_subscribe_topic_template,
        vol.Optional(CONF_PAYLOAD): cv.template,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
            vol.Coerce(int), vol.In([0, 1, 2])
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    topic = config[CONF_TOPIC]
    wanted_payload = config.get(CONF_PAYLOAD)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    encoding = config[CONF_ENCODING] or None
    qos = config[CONF_QOS]
    job = HassJob(action)
    variables = None
    if trigger_info:
        variables = trigger_info.get("variables")

    template.attach(hass, wanted_payload)
    if wanted_payload:
        wanted_payload = wanted_payload.async_render(
            variables, limited=True, parse_result=False
        )

    template.attach(hass, topic)
    if isinstance(topic, template.Template):
        topic = topic.async_render(variables, limited=True, parse_result=False)
        topic = mqtt.util.valid_subscribe_topic(topic)

    template.attach(hass, value_template)

    @callback
    def mqtt_automation_listener(mqttmsg):
        """Listen for MQTT messages."""
        payload = mqttmsg.payload

        if value_template is not None:
            payload = value_template.async_render_with_possible_json_value(
                payload,
                error_value=None,
            )

        if wanted_payload is None or wanted_payload == payload:
            data = {
                **trigger_data,
                "platform": "mqtt",
                "topic": mqttmsg.topic,
                "payload": mqttmsg.payload,
                "qos": mqttmsg.qos,
                "description": f"mqtt topic {mqttmsg.topic}",
            }

            with suppress(ValueError):
                data["payload_json"] = json_loads(mqttmsg.payload)

            hass.async_run_hass_job(job, {"trigger": data})

    _LOGGER.debug(
        "Attaching MQTT trigger for topic: '%s', payload: '%s'", topic, wanted_payload
    )

    remove = await mqtt.async_subscribe(
        hass, topic, mqtt_automation_listener, encoding=encoding, qos=qos
    )
    return remove
