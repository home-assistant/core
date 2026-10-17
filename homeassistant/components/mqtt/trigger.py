"""Offer MQTT listening automation rules."""

from collections.abc import Callable
from contextlib import suppress
import logging
from typing import Any

import probatio

from homeassistant.const import CONF_PAYLOAD, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.trigger import TriggerActionType, TriggerData, TriggerInfo
from homeassistant.helpers.trigger.template import async_track_trigger_template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.json import json_loads

from .client import async_subscribe_internal
from .const import (
    CONF_ENCODING,
    CONF_QOS,
    CONF_TOPIC,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    DOMAIN,
)
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
)
from .util import valid_subscribe_topic, valid_subscribe_topic_template

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_PLATFORM): DOMAIN,
        probatio.Required(CONF_TOPIC): valid_subscribe_topic_template,
        probatio.Optional(CONF_PAYLOAD): cv.template,
        probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
        probatio.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        probatio.Optional(CONF_QOS, default=DEFAULT_QOS): probatio.All(
            probatio.Coerce(int), probatio.In([0, 1, 2])
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
    ] = MqttCommandTemplate(config.get(CONF_PAYLOAD)).async_render
    value_template: Callable[[ReceivePayloadType, str], ReceivePayloadType]
    value_template = MqttValueTemplate(
        config.get(CONF_VALUE_TEMPLATE)
    ).async_render_with_possible_json_value
    encoding: str | None = config[CONF_ENCODING] or None
    qos: int = config[CONF_QOS]
    job = HassJob(action)
    variables: TemplateVarsType | None = None
    if trigger_info:
        variables = trigger_info.get("variables")

    wanted_payload = command_template(None, variables)

    topic: str
    unsubscribe_topic: CALLBACK_TYPE

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

    @callback
    def async_subscribe(topic: str) -> CALLBACK_TYPE:
        """Subscribe the trigger to a topic."""
        return async_subscribe_internal(
            hass,
            topic,
            mqtt_automation_listener,
            encoding=encoding,
            qos=qos,
            job_type=HassJobType.Callback,
        )

    @callback
    def async_topic_changed(new_topic: str) -> None:
        """Move the subscription to the newly rendered topic."""
        nonlocal topic, unsubscribe_topic

        if new_topic == topic:
            return

        try:
            valid_subscribe_topic(new_topic)
        except probatio.Invalid as err:
            _LOGGER.error(
                "Invalid MQTT trigger topic '%s' in %s, keeping topic '%s': %s",
                new_topic,
                trigger_info["name"],
                topic,
                err,
            )
            return

        _LOGGER.debug("Re-subscribing MQTT trigger from '%s' to '%s'", topic, new_topic)

        # Subscribe first, so no message is missed while switching topics.
        unsubscribe_new_topic = async_subscribe(new_topic)
        unsubscribe_topic()
        topic = new_topic
        unsubscribe_topic = unsubscribe_new_topic

    @callback
    def async_topic_error(err: TemplateError) -> None:
        """Keep the current subscription when the topic fails to render."""
        _LOGGER.error(
            "Error rendering MQTT trigger topic in %s, keeping topic '%s': %s",
            trigger_info["name"],
            topic,
            err,
        )

    topic, stop_tracking_topic = async_track_trigger_template(
        hass,
        config[CONF_TOPIC],
        variables,
        async_topic_changed,
        async_topic_error,
    )

    _LOGGER.debug(
        "Attaching MQTT trigger for topic: '%s', payload: '%s'", topic, wanted_payload
    )

    try:
        valid_subscribe_topic(topic)
        unsubscribe_topic = async_subscribe(topic)
    except Exception:
        stop_tracking_topic()
        raise

    @callback
    def async_remove() -> None:
        """Stop tracking the topic and unsubscribe."""
        stop_tracking_topic()
        unsubscribe_topic()

    return async_remove
