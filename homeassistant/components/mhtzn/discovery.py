"""Support for MQTT discovery."""
from __future__ import annotations

import asyncio
from collections import deque
import functools
import json
import logging
import re
import time

from homeassistant.const import CONF_DEVICE, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.loader import async_get_mqtt

from .. import mhtzn
from .abbreviations import ABBREVIATIONS, DEVICE_ABBREVIATIONS
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_AVAILABILITY,
    CONF_TOPIC,
    CONFIG_ENTRY_IS_SETUP,
    DATA_CONFIG_ENTRY_LOCK,
    DOMAIN, CONF_ENV_ID, DATA_MQTT,
)

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r"(?P<component>\w+)/(?:(?P<node_id>[a-zA-Z0-9_-]+)/)"
    r"?(?P<object_id>[a-zA-Z0-9_-]+)/config"
)

SUPPORTED_COMPONENTS = [
    "light",
    "switch",
    "cover",
]

ALREADY_DISCOVERED = "mqtt_discovered_components"
PENDING_DISCOVERED = "mqtt_pending_components"
DATA_CONFIG_FLOW_LOCK = "mqtt_discovery_config_flow_lock"
DISCOVERY_UNSUBSCRIBE = "mqtt_discovery_unsubscribe"
INTEGRATION_UNSUBSCRIBE = "mqtt_integration_discovery_unsubscribe"
MQTT_DISCOVERY_UPDATED = "mqtt_discovery_updated_{}"
MQTT_DISCOVERY_NEW = "mqtt_discovery_new_{}_{}"
MQTT_DISCOVERY_DONE = "mqtt_discovery_done_{}"
LAST_DISCOVERY = "mqtt_last_discovery"

TOPIC_BASE = "~"


class MQTTConfig(dict):
    """Dummy class to allow adding attributes."""

    discovery_data: dict


def clear_discovery_hash(hass: HomeAssistant, discovery_hash: tuple) -> None:
    """Clear entry in ALREADY_DISCOVERED list."""
    del hass.data[ALREADY_DISCOVERED][discovery_hash]


def set_discovery_hash(hass: HomeAssistant, discovery_hash: tuple):
    """Clear entry in ALREADY_DISCOVERED list."""
    hass.data[ALREADY_DISCOVERED][discovery_hash] = {}


async def async_start(  # noqa: C901
        hass: HomeAssistant, discovery_topic, env_id, config_entry=None
) -> None:
    """Start MQTT Discovery."""
    mqtt_integrations = {}

    async def async_discovery_message_received(msg):
        """Process the received message."""
        hass.data[LAST_DISCOVERY] = time.time()
        payload = msg.payload

        if payload:
            try:
                payload = json.loads(payload)
            except ValueError:
                _LOGGER.warning("Unable to parse JSON: '%s'", payload)
                return
        else:
            _LOGGER.warning("JSON None")
            return

        device_list = payload["data"]["list"]

        for device in device_list:
            device_name = device["name"]
            device_sn = device["sn"]
            device_type = device["devType"]
            if device_type == 1:
                await add_entity("light", device_name, device_sn)
            elif device_type == 3:
                await add_entity("cover", device_name, device_sn)
            '''
            elif device_type == 2:
                await add_entity("switch", device_name, device_sn)
            '''

    async def async_process_discovery_payload(component, discovery_id, payload):
        """Process the payload of a new discovery."""

        _LOGGER.debug("Process discovery payload %s", payload)
        discovery_hash = (component, discovery_id)
        if discovery_hash in hass.data[ALREADY_DISCOVERED] or payload:

            async def discovery_done(_):
                pending = hass.data[PENDING_DISCOVERED][discovery_hash]["pending"]
                _LOGGER.debug("Pending discovery for %s: %s", discovery_hash, pending)
                if not pending:
                    hass.data[PENDING_DISCOVERED][discovery_hash]["unsub"]()
                    hass.data[PENDING_DISCOVERED].pop(discovery_hash)
                else:
                    payload = pending.pop()
                    await async_process_discovery_payload(
                        component, discovery_id, payload
                    )

            if discovery_hash not in hass.data[PENDING_DISCOVERED]:
                hass.data[PENDING_DISCOVERED][discovery_hash] = {
                    "unsub": async_dispatcher_connect(
                        hass,
                        MQTT_DISCOVERY_DONE.format(discovery_hash),
                        discovery_done,
                    ),
                    "pending": deque([]),
                }

        if discovery_hash in hass.data[ALREADY_DISCOVERED]:
            # Dispatch update
            _LOGGER.info(
                "Component has already been discovered: %s %s, sending update",
                component,
                discovery_id,
            )
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(discovery_hash), payload
            )
        elif payload:
            # Add component
            _LOGGER.info("Found new component: %s %s", component, discovery_id)
            hass.data[ALREADY_DISCOVERED][discovery_hash] = None

            config_entries_key = f"{component}.mqtt"
            async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
                if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                    if component == "device_automation":
                        # Local import to avoid circular dependencies
                        # pylint: disable-next=import-outside-toplevel
                        from . import device_automation

                        await device_automation.async_setup_entry(hass, config_entry)
                    elif component == "tag":
                        # Local import to avoid circular dependencies
                        # pylint: disable-next=import-outside-toplevel
                        from . import tag

                        await tag.async_setup_entry(hass, config_entry)
                    else:
                        await hass.config_entries.async_forward_entry_setup(
                            config_entry, component
                        )
                    hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

            async_dispatcher_send(
                hass, MQTT_DISCOVERY_NEW.format(component, "mqtt"), payload
            )
        else:
            # Unhandled discovery message
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )

    async def add_entity(component, device_name, device_sn, key_num=None) -> None:

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Integration %s is not supported", component)
            return

        unique_id = device_sn

        payload = {
            "name": device_name,
            "object_id": unique_id,
            "unique_id": unique_id,
            "env_id": env_id,
            "key_num": key_num
        }

        topic = f"{discovery_topic}/unique_id/config"

        if component == "switch":
            payload["command_topic"] = f"P/{env_id}/center/q19"
        elif component == "light":
            payload["command_topic"] = f"P/{env_id}/center/q20"
            payload["schema"] = "json"
            payload["brightness"] = True
            payload["color_mode"] = True
            payload["min_mireds"] = 2700
            payload["max_mireds"] = 6500
            payload["supported_color_modes"] = ["color_temp", "rgb"]
        elif component == "cover":
            payload["command_topic"] = f"P/{env_id}/center/q21"
            payload["set_position_topic"] = f"P/{env_id}/center/q21"
            payload["position_topic"] = f"P/{env_id}/center/q21"

        payload = MQTTConfig(payload)

        for key in list(payload):
            abbreviated_key = key
            key = ABBREVIATIONS.get(key, key)
            payload[key] = payload.pop(abbreviated_key)

        if CONF_DEVICE in payload:
            device = payload[CONF_DEVICE]
            for key in list(device):
                abbreviated_key = key
                key = DEVICE_ABBREVIATIONS.get(key, key)
                device[key] = device.pop(abbreviated_key)

        if TOPIC_BASE in payload:
            base = payload.pop(TOPIC_BASE)
            for key, value in payload.items():
                if isinstance(value, str) and value:
                    if value[0] == TOPIC_BASE and key.endswith("topic"):
                        payload[key] = f"{base}{value[1:]}"
                    if value[-1] == TOPIC_BASE and key.endswith("topic"):
                        payload[key] = f"{value[:-1]}{base}"
            if payload.get(CONF_AVAILABILITY):
                for availability_conf in cv.ensure_list(payload[CONF_AVAILABILITY]):
                    if not isinstance(availability_conf, dict):
                        continue
                    if topic := availability_conf.get(CONF_TOPIC):
                        if topic[0] == TOPIC_BASE:
                            availability_conf[CONF_TOPIC] = f"{base}{topic[1:]}"
                        if topic[-1] == TOPIC_BASE:
                            availability_conf[CONF_TOPIC] = f"{topic[:-1]}{base}"

        payload = MQTTConfig(payload)

        discovery_id = unique_id

        discovery_hash = (component, discovery_id)

        if payload:
            # Attach MQTT topic to the payload, used for debug prints
            setattr(payload, "__configuration_source__", f"MQTT (topic: '{topic}')")
            discovery_data = {
                ATTR_DISCOVERY_HASH: discovery_hash,
                ATTR_DISCOVERY_PAYLOAD: payload,
                ATTR_DISCOVERY_TOPIC: topic,
            }
            setattr(payload, "discovery_data", discovery_data)

            payload[CONF_PLATFORM] = "mqtt"

        if discovery_hash in hass.data[PENDING_DISCOVERED]:
            pending = hass.data[PENDING_DISCOVERED][discovery_hash]["pending"]
            pending.appendleft(payload)
            _LOGGER.warning(
                "Component has already been discovered: %s %s, queuing update",
                component,
                discovery_id,
            )
            return

        await async_process_discovery_payload(component, discovery_id, payload)

    hass.data[DATA_CONFIG_FLOW_LOCK] = asyncio.Lock()

    hass.data[ALREADY_DISCOVERED] = {}
    hass.data[PENDING_DISCOVERED] = {}

    # discovery_topics = [
    #     f"{discovery_topic}/+/+/config",
    #     f"{discovery_topic}/+/+/+/config",
    # ]
    # hass.data[DISCOVERY_UNSUBSCRIBE] = await asyncio.gather(
    #     *(
    #         mhtzn.async_subscribe(hass, topic, async_discovery_message_received, 0)
    #         for topic in discovery_topics
    #     )
    # )

    async def query_device_async_subscribe():
        await mhtzn.async_subscribe(hass, f"{discovery_topic}/center/p5", async_discovery_message_received, 0)

    async def query_device_async_publish():
        await asyncio.sleep(5)
        query_device_topic = f"P/{env_id}/center/q5"
        query_device_payload = {
            "seq": 1,
            "rspTo": discovery_topic,
            "data": {}
        }
        await hass.data[DATA_MQTT].async_publish(query_device_topic, json.dumps(query_device_payload), 0, False)

    hass.data[DISCOVERY_UNSUBSCRIBE] = await asyncio.gather(
        query_device_async_subscribe(),
        query_device_async_publish()
    )

    hass.data[LAST_DISCOVERY] = time.time()
    mqtt_integrations = await async_get_mqtt(hass)

    hass.data[INTEGRATION_UNSUBSCRIBE] = {}

    for (integration, topics) in mqtt_integrations.items():

        async def async_integration_message_received(integration, msg):
            """Process the received message."""
            key = f"{integration}_{msg.subscribed_topic}"

            # Lock to prevent initiating many parallel config flows.
            # Note: The lock is not intended to prevent a race, only for performance
            async with hass.data[DATA_CONFIG_FLOW_LOCK]:
                # Already unsubscribed
                if key not in hass.data[INTEGRATION_UNSUBSCRIBE]:
                    return

                data = mhtzn.MqttServiceInfo(
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
                        and result["type"] == RESULT_TYPE_ABORT
                        and result["reason"]
                        in ("already_configured", "single_instance_allowed")
                ):
                    unsub = hass.data[INTEGRATION_UNSUBSCRIBE].pop(key, None)
                    if unsub is None:
                        return
                    unsub()

        for topic in topics:
            key = f"{integration}_{topic}"
            hass.data[INTEGRATION_UNSUBSCRIBE][key] = await mhtzn.async_subscribe(
                hass,
                topic,
                functools.partial(async_integration_message_received, integration),
                0,
            )


async def async_stop(hass: HomeAssistant) -> None:
    """Stop MQTT Discovery."""
    if DISCOVERY_UNSUBSCRIBE in hass.data:
        for unsub in hass.data[DISCOVERY_UNSUBSCRIBE]:
            unsub()
        hass.data[DISCOVERY_UNSUBSCRIBE] = []
    if INTEGRATION_UNSUBSCRIBE in hass.data:
        for key, unsub in list(hass.data[INTEGRATION_UNSUBSCRIBE].items()):
            unsub()
            hass.data[INTEGRATION_UNSUBSCRIBE].pop(key)
