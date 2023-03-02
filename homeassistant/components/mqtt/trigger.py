"""Offer MQTT listening automation rules."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_PAYLOAD, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger import TriggerActionType, TriggerData, TriggerInfo
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.json import json_loads

from .. import mqtt
from .const import CONF_ENCODING, CONF_QOS, CONF_TOPIC, DEFAULT_ENCODING, DEFAULT_QOS
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)

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
    trigger_data: TriggerData = trigger_info["trigger_data"]
    command_template: Callable[
        [PublishPayloadType, TemplateVarsType], PublishPayloadType
    ] = MqttCommandTemplate(config.get(CONF_PAYLOAD), hass=hass).async_render
    value_template: Callable[[ReceivePayloadType, str], ReceivePayloadType]
    value_template = MqttValueTemplate(
        config.get(CONF_VALUE_TEMPLATE), hass=hass
    ).async_render_with_possible_json_value
    encoding: str | None = config[CONF_ENCODING] or None
    qos: int = config[CONF_QOS]
    job = HassJob(action)
    variables: TemplateVarsType | None = None
    if trigger_info:
        variables = trigger_info.get("variables")

    wanted_payload = command_template(None, variables)

    topic_template: Template = config[CONF_TOPIC]
    topic_template.hass = hass
    topic = topic_template.async_render(variables, limited=True, parse_result=False)
    mqtt.util.valid_subscribe_topic(topic)

    @callback
    def mqtt_automation_listener(mqttmsg: ReceiveMessage) -> None:
        """Listen for MQTT messages."""
        if wanted_payload is None or (
            (payload := value_template(mqttmsg.payload, PayloadSentinel.DEFAULT))
            and payload is not PayloadSentinel.DEFAULT
            and wanted_payload == payload
        ):
            data: dict[str, Any] = {
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
