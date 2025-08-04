"""Offer MQTT listening automation rules."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DATA, CONF_PAYLOAD, CONF_VALUE_TEMPLATE
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionType,
    TriggerData,
    TriggerInfo,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.json import json_loads

from .client import async_subscribe_internal
from .const import CONF_ENCODING, CONF_QOS, CONF_TOPIC, DEFAULT_ENCODING, DEFAULT_QOS
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
)
from .util import valid_subscribe_topic, valid_subscribe_topic_template

_LOGGER = logging.getLogger(__name__)


_DATA_SCHEMA_DICT = {
    vol.Required(CONF_TOPIC): valid_subscribe_topic_template,
    vol.Optional(CONF_PAYLOAD): cv.template,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
    vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
        vol.Coerce(int), vol.In([0, 1, 2])
    ),
}

_DATA_SCHEMA = vol.Schema(_DATA_SCHEMA_DICT)


class MqttTrigger(Trigger):
    """MQTT trigger."""

    has_target = False

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = config.copy()
        data = config.setdefault(CONF_DATA, {})
        # Move top-level keys to data
        for key_marked in _DATA_SCHEMA_DICT:
            key = key_marked.schema
            if key in config:
                if key in data:
                    raise vol.Invalid(
                        f"'{key}' cannot be specified in both top-level and data"
                    )
                data[key] = config.pop(key)
        return await super().async_validate_config(hass, config)

    @classmethod
    async def async_validate_data(cls, hass: HomeAssistant, data: Any) -> Any:
        """Validate data."""
        return _DATA_SCHEMA(data)

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize trigger."""
        self._hass = hass
        self._data = config[CONF_DATA]

    async def async_attach(
        self,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Listen for state changes based on configuration."""
        trigger_data: TriggerData = trigger_info["trigger_data"]
        command_template: Callable[
            [PublishPayloadType, TemplateVarsType], PublishPayloadType
        ] = MqttCommandTemplate(self._data.get(CONF_PAYLOAD)).async_render
        value_template: Callable[[ReceivePayloadType, str], ReceivePayloadType]
        value_template = MqttValueTemplate(
            self._data.get(CONF_VALUE_TEMPLATE)
        ).async_render_with_possible_json_value
        encoding: str | None = self._data[CONF_ENCODING] or None
        qos: int = self._data[CONF_QOS]
        job = HassJob(action)
        variables: TemplateVarsType | None = None
        if trigger_info:
            variables = trigger_info.get("variables")

        wanted_payload = command_template(None, variables)

        topic_template: Template = self._data[CONF_TOPIC]
        topic = topic_template.async_render(variables, limited=True, parse_result=False)
        valid_subscribe_topic(topic)

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

                self._hass.async_run_hass_job(job, {"trigger": data})

        _LOGGER.debug(
            "Attaching MQTT trigger for topic: '%s', payload: '%s'",
            topic,
            wanted_payload,
        )

        return async_subscribe_internal(
            self._hass,
            topic,
            mqtt_automation_listener,
            encoding=encoding,
            qos=qos,
            job_type=HassJobType.Callback,
        )


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers provided by this integration."""
    return {"_": MqttTrigger}
