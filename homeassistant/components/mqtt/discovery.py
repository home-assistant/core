"""Support for MQTT discovery."""
from __future__ import annotations

import asyncio
from collections import deque
import functools
import logging
import re
import time
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_mqtt
from homeassistant.util.json import json_loads_object

from .. import mqtt
from .abbreviations import ABBREVIATIONS, DEVICE_ABBREVIATIONS, ORIGIN_ABBREVIATIONS
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_AVAILABILITY,
    CONF_ORIGIN,
    CONF_SUPPORT_URL,
    CONF_SW_VERSION,
    CONF_TOPIC,
    DOMAIN,
)
from .models import MqttOriginInfo, ReceiveMessage
from .util import get_mqtt_data

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r"(?P<component>\w+)/(?:(?P<node_id>[a-zA-Z0-9_-]+)/)"
    r"?(?P<object_id>[a-zA-Z0-9_-]+)/config"
)

SUPPORTED_COMPONENTS = {
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "device_automation",
    "device_tracker",
    "event",
    "fan",
    "humidifier",
    "image",
    "lawn_mower",
    "light",
    "lock",
    "number",
    "scene",
    "siren",
    "select",
    "sensor",
    "switch",
    "tag",
    "text",
    "update",
    "vacuum",
    "water_heater",
}

MQTT_DISCOVERY_UPDATED = "mqtt_discovery_updated_{}"
MQTT_DISCOVERY_NEW = "mqtt_discovery_new_{}_{}"
MQTT_DISCOVERY_DONE = "mqtt_discovery_done_{}"

TOPIC_BASE = "~"

MQTT_ORIGIN_INFO_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_SW_VERSION): cv.string,
            vol.Optional(CONF_SUPPORT_URL): cv.configuration_url,
        }
    ),
)


class MQTTDiscoveryPayload(dict[str, Any]):
    """Class to hold and MQTT discovery payload and discovery data."""

    discovery_data: DiscoveryInfoType


def clear_discovery_hash(hass: HomeAssistant, discovery_hash: tuple[str, str]) -> None:
    """Clear entry from already discovered list."""
    get_mqtt_data(hass).discovery_already_discovered.remove(discovery_hash)


def set_discovery_hash(hass: HomeAssistant, discovery_hash: tuple[str, str]) -> None:
    """Add entry to already discovered list."""
    get_mqtt_data(hass).discovery_already_discovered.add(discovery_hash)


@callback
def async_log_discovery_origin_info(
    message: str, discovery_payload: MQTTDiscoveryPayload
) -> None:
    """Log information about the discovery and origin."""
    if CONF_ORIGIN not in discovery_payload:
        _LOGGER.info(message)
        return
    origin_info: MqttOriginInfo = discovery_payload[CONF_ORIGIN]
    sw_version_log = ""
    if sw_version := origin_info.get("sw_version"):
        sw_version_log = f", version: {sw_version}"
    support_url_log = ""
    if support_url := origin_info.get("support_url"):
        support_url_log = f", support URL: {support_url}"
    _LOGGER.info(
        "%s from external application %s%s%s",
        message,
        origin_info["name"],
        sw_version_log,
        support_url_log,
    )


async def async_start(  # noqa: C901
    hass: HomeAssistant, discovery_topic: str, config_entry: ConfigEntry
) -> None:
    """Start MQTT Discovery."""
    mqtt_data = get_mqtt_data(hass)
    mqtt_integrations = {}

    @callback
    def async_discovery_message_received(msg: ReceiveMessage) -> None:  # noqa: C901
        """Process the received message."""
        mqtt_data.last_discovery = time.time()
        payload = msg.payload
        topic = msg.topic
        topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)

        if not (match := TOPIC_MATCHER.match(topic_trimmed)):
            if topic_trimmed.endswith("config"):
                _LOGGER.warning(
                    (
                        "Received message on illegal discovery topic '%s'. The topic"
                        " contains "
                        "not allowed characters. For more information see "
                        "https://www.home-assistant.io/integrations/mqtt/#discovery-topic"
                    ),
                    topic,
                )
            return

        component, node_id, object_id = match.groups()

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Integration %s is not supported", component)
            return

        if payload:
            try:
                discovery_payload = MQTTDiscoveryPayload(json_loads_object(payload))
            except ValueError:
                _LOGGER.warning("Unable to parse JSON %s: '%s'", object_id, payload)
                return
        else:
            discovery_payload = MQTTDiscoveryPayload({})

        for key in list(discovery_payload):
            abbreviated_key = key
            key = ABBREVIATIONS.get(key, key)
            discovery_payload[key] = discovery_payload.pop(abbreviated_key)

        if CONF_DEVICE in discovery_payload:
            device = discovery_payload[CONF_DEVICE]
            for key in list(device):
                abbreviated_key = key
                key = DEVICE_ABBREVIATIONS.get(key, key)
                device[key] = device.pop(abbreviated_key)

        if CONF_ORIGIN in discovery_payload:
            origin_info: dict[str, Any] = discovery_payload[CONF_ORIGIN]
            try:
                for key in list(origin_info):
                    abbreviated_key = key
                    key = ORIGIN_ABBREVIATIONS.get(key, key)
                    origin_info[key] = origin_info.pop(abbreviated_key)
                MQTT_ORIGIN_INFO_SCHEMA(discovery_payload[CONF_ORIGIN])
            except Exception:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Unable to parse origin information "
                    "from discovery message, got %s",
                    discovery_payload[CONF_ORIGIN],
                )
                return

        if CONF_AVAILABILITY in discovery_payload:
            for availability_conf in cv.ensure_list(
                discovery_payload[CONF_AVAILABILITY]
            ):
                if isinstance(availability_conf, dict):
                    for key in list(availability_conf):
                        abbreviated_key = key
                        key = ABBREVIATIONS.get(key, key)
                        availability_conf[key] = availability_conf.pop(abbreviated_key)

        if TOPIC_BASE in discovery_payload:
            base = discovery_payload.pop(TOPIC_BASE)
            for key, value in discovery_payload.items():
                if isinstance(value, str) and value:
                    if value[0] == TOPIC_BASE and key.endswith("topic"):
                        discovery_payload[key] = f"{base}{value[1:]}"
                    if value[-1] == TOPIC_BASE and key.endswith("topic"):
                        discovery_payload[key] = f"{value[:-1]}{base}"
            if discovery_payload.get(CONF_AVAILABILITY):
                for availability_conf in cv.ensure_list(
                    discovery_payload[CONF_AVAILABILITY]
                ):
                    if not isinstance(availability_conf, dict):
                        continue
                    if topic := str(availability_conf.get(CONF_TOPIC)):
                        if topic[0] == TOPIC_BASE:
                            availability_conf[CONF_TOPIC] = f"{base}{topic[1:]}"
                        if topic[-1] == TOPIC_BASE:
                            availability_conf[CONF_TOPIC] = f"{topic[:-1]}{base}"

        # If present, the node_id will be included in the discovered object id
        discovery_id = " ".join((node_id, object_id)) if node_id else object_id
        discovery_hash = (component, discovery_id)

        if discovery_payload:
            # Attach MQTT topic to the payload, used for debug prints
            setattr(
                discovery_payload,
                "__configuration_source__",
                f"MQTT (topic: '{topic}')",
            )
            discovery_data = {
                ATTR_DISCOVERY_HASH: discovery_hash,
                ATTR_DISCOVERY_PAYLOAD: discovery_payload,
                ATTR_DISCOVERY_TOPIC: topic,
            }
            setattr(discovery_payload, "discovery_data", discovery_data)

            discovery_payload[CONF_PLATFORM] = "mqtt"

        if discovery_hash in mqtt_data.discovery_pending_discovered:
            pending = mqtt_data.discovery_pending_discovered[discovery_hash]["pending"]
            pending.appendleft(discovery_payload)
            _LOGGER.debug(
                "Component has already been discovered: %s %s, queuing update",
                component,
                discovery_id,
            )
            return

        async_process_discovery_payload(component, discovery_id, discovery_payload)

    @callback
    def async_process_discovery_payload(
        component: str, discovery_id: str, payload: MQTTDiscoveryPayload
    ) -> None:
        """Process the payload of a new discovery."""

        _LOGGER.debug("Process discovery payload %s", payload)
        discovery_hash = (component, discovery_id)

        already_discovered = discovery_hash in mqtt_data.discovery_already_discovered
        if (
            already_discovered or payload
        ) and discovery_hash not in mqtt_data.discovery_pending_discovered:
            discovery_pending_discovered = mqtt_data.discovery_pending_discovered

            @callback
            def discovery_done(_: Any) -> None:
                pending = discovery_pending_discovered[discovery_hash]["pending"]
                _LOGGER.debug("Pending discovery for %s: %s", discovery_hash, pending)
                if not pending:
                    discovery_pending_discovered[discovery_hash]["unsub"]()
                    discovery_pending_discovered.pop(discovery_hash)
                else:
                    payload = pending.pop()
                    async_process_discovery_payload(component, discovery_id, payload)

            discovery_pending_discovered[discovery_hash] = {
                "unsub": async_dispatcher_connect(
                    hass,
                    MQTT_DISCOVERY_DONE.format(discovery_hash),
                    discovery_done,
                ),
                "pending": deque([]),
            }

        if already_discovered:
            # Dispatch update
            message = f"Component has already been discovered: {component} {discovery_id}, sending update"
            async_log_discovery_origin_info(message, payload)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), payload
            )
        elif payload:
            # Add component
            message = f"Found new component: {component} {discovery_id}"
            async_log_discovery_origin_info(message, payload)
            mqtt_data.discovery_already_discovered.add(discovery_hash)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_NEW.format(component, "mqtt"), payload
            )
        else:
            # Unhandled discovery message
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )

    discovery_topics = [
        f"{discovery_topic}/+/+/config",
        f"{discovery_topic}/+/+/+/config",
    ]
    mqtt_data.discovery_unsubscribe = await asyncio.gather(
        *(
            mqtt.async_subscribe(hass, topic, async_discovery_message_received, 0)
            for topic in discovery_topics
        )
    )

    mqtt_data.last_discovery = time.time()
    mqtt_integrations = await async_get_mqtt(hass)

    for integration, topics in mqtt_integrations.items():

        async def async_integration_message_received(
            integration: str, msg: ReceiveMessage
        ) -> None:
            """Process the received message."""
            if TYPE_CHECKING:
                assert mqtt_data.data_config_flow_lock
            key = f"{integration}_{msg.subscribed_topic}"

            # Lock to prevent initiating many parallel config flows.
            # Note: The lock is not intended to prevent a race, only for performance
            async with mqtt_data.data_config_flow_lock:
                # Already unsubscribed
                if key not in mqtt_data.integration_unsubscribe:
                    return

                data = MqttServiceInfo(
                    topic=msg.topic,
                    payload=msg.payload,
                    qos=msg.qos,
                    retain=msg.retain,
                    subscribed_topic=msg.subscribed_topic,
                    timestamp=msg.timestamp,
                )
                result = await hass.config_entries.flow.async_init(
                    integration, context={"source": DOMAIN}, data=data
                )
                if (
                    result
                    and result["type"] == FlowResultType.ABORT
                    and result["reason"]
                    in ("already_configured", "single_instance_allowed")
                ):
                    mqtt_data.integration_unsubscribe.pop(key)()

        for topic in topics:
            key = f"{integration}_{topic}"
            mqtt_data.integration_unsubscribe[key] = await mqtt.async_subscribe(
                hass,
                topic,
                functools.partial(async_integration_message_received, integration),
                0,
            )


async def async_stop(hass: HomeAssistant) -> None:
    """Stop MQTT Discovery."""
    mqtt_data = get_mqtt_data(hass)
    for unsub in mqtt_data.discovery_unsubscribe:
        unsub()
    mqtt_data.discovery_unsubscribe = []
    for key, unsub in list(mqtt_data.integration_unsubscribe.items()):
        unsub()
        mqtt_data.integration_unsubscribe.pop(key)
