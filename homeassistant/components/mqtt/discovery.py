"""Support for MQTT discovery."""

from __future__ import annotations

import asyncio
from collections import deque
import functools
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_PLATFORM
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo, ReceivePayloadType
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_mqtt
from homeassistant.util.json import json_loads_object
from homeassistant.util.signal_type import SignalTypeFormat

from .. import mqtt
from .abbreviations import ABBREVIATIONS, DEVICE_ABBREVIATIONS, ORIGIN_ABBREVIATIONS
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_AVAILABILITY,
    CONF_COMPONENTS,
    CONF_ORIGIN,
    CONF_TOPIC,
    DOMAIN,
    SUPPORTED_COMPONENTS,
)
from .models import DATA_MQTT, MqttOriginInfo, ReceiveMessage
from .schemas import MQTT_ORIGIN_INFO_SCHEMA
from .util import async_forward_entry_setup_and_setup_discovery

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r"(?P<component>\w+)/(?:(?P<node_id>[a-zA-Z0-9_-]+)/)"
    r"?(?P<object_id>[a-zA-Z0-9_-]+)/config"
)

MQTT_DISCOVERY_UPDATED: SignalTypeFormat[MQTTDiscoveryPayload] = SignalTypeFormat(
    "mqtt_discovery_updated_{}_{}"
)
MQTT_DISCOVERY_NEW: SignalTypeFormat[MQTTDiscoveryPayload] = SignalTypeFormat(
    "mqtt_discovery_new_{}_{}"
)
MQTT_DISCOVERY_NEW_COMPONENT = "mqtt_discovery_new_component"
MQTT_DISCOVERY_DONE: SignalTypeFormat[Any] = SignalTypeFormat(
    "mqtt_discovery_done_{}_{}"
)

TOPIC_BASE = "~"


class MQTTDiscoveryPayload(dict[str, Any]):
    """Class to hold and MQTT discovery payload and discovery data."""

    device_discovery: bool = False
    discovery_data: DiscoveryInfoType


def clear_discovery_hash(hass: HomeAssistant, discovery_hash: tuple[str, str]) -> None:
    """Clear entry from already discovered list."""
    hass.data[DATA_MQTT].discovery_already_discovered.remove(discovery_hash)


def set_discovery_hash(hass: HomeAssistant, discovery_hash: tuple[str, str]) -> None:
    """Add entry to already discovered list."""
    hass.data[DATA_MQTT].discovery_already_discovered.add(discovery_hash)


@callback
def async_log_discovery_origin_info(
    message: str, discovery_payload: MQTTDiscoveryPayload, level: int = logging.INFO
) -> None:
    """Log information about the discovery and origin."""
    # We only log origin info once per device discovery
    if discovery_payload.device_discovery:
        _LOGGER.info(message)
        return
    if CONF_ORIGIN not in discovery_payload:
        _LOGGER.log(level, message)
        return
    origin_info: MqttOriginInfo = discovery_payload[CONF_ORIGIN]
    sw_version_log = ""
    if sw_version := origin_info.get("sw_version"):
        sw_version_log = f", version: {sw_version}"
    support_url_log = ""
    if support_url := origin_info.get("support_url"):
        support_url_log = f", support URL: {support_url}"
    _LOGGER.log(
        level,
        "%s from external application %s%s%s",
        message,
        origin_info["name"],
        sw_version_log,
        support_url_log,
    )


@callback
def _replace_all_abbreviations(discovery_payload: Any | dict[str, Any]) -> None:
    """Replace all abbreviations in an MQTT discovery payload."""

    @callback
    def _replace_abbreviations(
        discovery_payload: Any | dict[str, Any], abbreviations: dict[str, str]
    ) -> None:
        """Replace abbreviations in an MQTT discovery payload."""
        if not isinstance(discovery_payload, dict):
            return
        for key in list(discovery_payload):
            abbreviated_key = key
            key = abbreviations.get(key, key)
            discovery_payload[key] = discovery_payload.pop(abbreviated_key)

    _replace_abbreviations(discovery_payload, ABBREVIATIONS)

    if CONF_ORIGIN in discovery_payload:
        origin_info: dict[str, Any] = discovery_payload[CONF_ORIGIN]
        _replace_abbreviations(origin_info, ORIGIN_ABBREVIATIONS)

    if CONF_DEVICE in discovery_payload:
        _replace_abbreviations(discovery_payload[CONF_DEVICE], DEVICE_ABBREVIATIONS)

    if CONF_AVAILABILITY in discovery_payload:
        for availability_conf in cv.ensure_list(discovery_payload[CONF_AVAILABILITY]):
            _replace_abbreviations(availability_conf, ABBREVIATIONS)


@callback
def _replace_topic_base(discovery_payload: dict[str, Any]) -> None:
    """Replace topic base in MQTT discovery data."""
    base = discovery_payload.pop(TOPIC_BASE)
    for key, value in discovery_payload.items():
        if isinstance(value, str) and value:
            if value[0] == TOPIC_BASE and key.endswith("topic"):
                discovery_payload[key] = f"{base}{value[1:]}"
            if value[-1] == TOPIC_BASE and key.endswith("topic"):
                discovery_payload[key] = f"{value[:-1]}{base}"
    if discovery_payload.get(CONF_AVAILABILITY):
        for availability_conf in cv.ensure_list(discovery_payload[CONF_AVAILABILITY]):
            if not isinstance(availability_conf, dict):
                continue
            if topic := str(availability_conf.get(CONF_TOPIC)):
                if topic[0] == TOPIC_BASE:
                    availability_conf[CONF_TOPIC] = f"{base}{topic[1:]}"
                if topic[-1] == TOPIC_BASE:
                    availability_conf[CONF_TOPIC] = f"{topic[:-1]}{base}"


@callback
def _generate_device_cleanup_config(
    hass: HomeAssistant, object_id: str, node_id: str | None
) -> dict[str, Any]:
    """Generate a cleanup message on device cleanup."""
    mqtt_data = get_mqtt_data(hass)
    device_discover_id: str = f"{node_id} {object_id}" if node_id else object_id
    config: dict[str, Any] = {CONF_DEVICE: {}, CONF_COMPONENTS: {}}
    comp_config = config[CONF_COMPONENTS]
    for platform, discover_id in mqtt_data.discovery_already_discovered:
        ids = discover_id.split(" ")
        comp_id = ids.pop(0)
        component_device_discover_id = " ".join(ids)
        if not ids:
            continue
        if device_discover_id == component_device_discover_id:
            comp_config[comp_id] = {CONF_PLATFORM: platform}

    return config if comp_config else {}


@callback
def _parse_device_payload(
    hass: HomeAssistant,
    payload: ReceivePayloadType,
    object_id: str,
    node_id: str | None,
) -> dict[str, Any]:
    """Parse a device discovery payload."""
    device_payload: dict[str, Any] = {}
    if payload == "":
        if not (
            device_payload := _generate_device_cleanup_config(hass, object_id, node_id)
        ):
            _LOGGER.warning(
                "No device components to cleanup for %s, node_id '%s'",
                object_id,
                node_id,
            )
        return device_payload
    try:
        device_payload = MQTTDiscoveryPayload(json_loads_object(payload))
    except ValueError:
        _LOGGER.warning("Unable to parse JSON %s: '%s'", object_id, payload)
        return {}
    try:
        _replace_all_abbreviations(device_payload)
        DEVICE_DISCOVERY_SCHEMA(device_payload)
    except vol.Invalid as exc:
        _LOGGER.warning(
            "Invalid MQTT device discovery payload for %s, %s: '%s'",
            object_id,
            exc,
            payload,
        )
        return {}
    return device_payload


@callback
def _valid_origin_info(discovery_payload: MQTTDiscoveryPayload) -> bool:
    """Parse and validate origin info from a single component discovery payload."""
    if CONF_ORIGIN not in discovery_payload:
        return True
    try:
        MQTT_ORIGIN_INFO_SCHEMA(discovery_payload[CONF_ORIGIN])
    except Exception as exc:  # noqa:BLE001
        _LOGGER.warning(
            "Unable to parse origin information " "from discovery message: %s, got %s",
            exc,
            discovery_payload[CONF_ORIGIN],
        )
        return False
    return True


@callback
def _merge_common_options(
    component_config: MQTTDiscoveryPayload, device_config: dict[str, Any]
) -> None:
    """Merge common options with the component config options."""
    for option in SHARED_OPTIONS:
        if option in device_config and option not in component_config:
            component_config[option] = device_config.get(option)


async def async_start(  # noqa: C901
    hass: HomeAssistant, discovery_topic: str, config_entry: ConfigEntry
) -> None:
    """Start MQTT Discovery."""
    mqtt_data = hass.data[DATA_MQTT]
    platform_setup_lock: dict[str, asyncio.Lock] = {}

    async def _async_component_setup(discovery_payload: MQTTDiscoveryPayload) -> None:
        """Perform component set up."""
        discovery_hash = discovery_payload.discovery_data[ATTR_DISCOVERY_HASH]
        component, discovery_id = discovery_hash
        platform_setup_lock.setdefault(component, asyncio.Lock())
        async with platform_setup_lock[component]:
            if component not in mqtt_data.platforms_loaded:
                await async_forward_entry_setup_and_setup_discovery(
                    hass, config_entry, {component}
                )
        # Add component
        message = f"Found new component: {component} {discovery_id}"
        async_log_discovery_origin_info(message, discovery_payload)
        mqtt_data.discovery_already_discovered.add(discovery_hash)
        async_dispatcher_send(
            hass, MQTT_DISCOVERY_NEW.format(component, "mqtt"), discovery_payload
        )

    mqtt_data.reload_dispatchers.append(
        async_dispatcher_connect(
            hass, MQTT_DISCOVERY_NEW_COMPONENT, _async_component_setup
        )
    )

    @callback
    def async_discovery_message_received(msg: ReceiveMessage) -> None:  # noqa: C901
        """Process the received message."""
        mqtt_data.last_discovery = time.monotonic()
        payload = msg.payload
        topic = msg.topic
        topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)

        if not (match := TOPIC_MATCHER.match(topic_trimmed)):
            if topic_trimmed.endswith("config"):
                _LOGGER.warning(
                    (
                        "Received message on illegal discovery topic '%s'. The topic"
                        " contains not allowed characters. For more information see "
                        "https://www.home-assistant.io/integrations/mqtt/#discovery-topic"
                    ),
                    topic,
                )
            return

        component, node_id, object_id = match.groups()

        discovered_components: list[MqttComponentConfig] = []
        if component == CONF_DEVICE:
            # Process device based discovery message
            device_discovery_payload = _parse_device_payload(
                hass, payload, object_id, node_id
            )
            if not device_discovery_payload:
                return
            device_config: dict[str, Any] = device_discovery_payload[CONF_DEVICE]
            origin_config: dict[str, Any] | None = device_discovery_payload.get(
                CONF_ORIGIN
            )
            component_configs: dict[str, Any] = device_discovery_payload[
                CONF_COMPONENTS
            ]
            for component_id, config in component_configs.items():
                component = config.pop(CONF_PLATFORM)
                component_node_id = (
                    f"{component_id} {node_id}" if node_id else component_id
                )
                _replace_all_abbreviations(config)
                discovery_payload = MQTTDiscoveryPayload(config)
                if discovery_payload:
                    discovery_payload.device_discovery = True
                    discovery_payload[CONF_DEVICE] = device_config
                    discovery_payload[CONF_ORIGIN] = origin_config
                    # Only assign shared config options
                    # when they are not set at entity level
                    _merge_common_options(discovery_payload, device_discovery_payload)
                discovered_components.append(
                    MqttComponentConfig(
                        component, object_id, component_node_id, discovery_payload
                    )
                )
            _LOGGER.debug(
                "Process device discovery payload %s", device_discovery_payload
            )
            device_discovery_id = f"{node_id} {object_id}" if node_id else object_id
            message = f"Processing device discovery for '{device_discovery_id}'"
            async_log_discovery_origin_info(
                message, MQTTDiscoveryPayload(device_discovery_payload)
            )

        else:
            # Process component based discovery message
            try:
                discovery_payload = MQTTDiscoveryPayload(
                    json_loads_object(payload) if payload else {}
                )
            except ValueError:
                _LOGGER.warning("Unable to parse JSON %s: '%s'", object_id, payload)
                return
            _replace_all_abbreviations(discovery_payload)
            if not _valid_origin_info(discovery_payload):
                return
            discovered_components.append(
                MqttComponentConfig(component, object_id, node_id, discovery_payload)
            )

        for component_config in discovered_components:
            component = component_config.component
            node_id = component_config.node_id
            object_id = component_config.object_id
            discovery_payload = component_config.discovery_payload
            if component not in SUPPORTED_COMPONENTS:
                _LOGGER.warning("Integration %s is not supported", component)
                return

            if TOPIC_BASE in discovery_payload:
                _replace_topic_base(discovery_payload)

            # If present, the node_id will be included in the discovered object id
            discovery_id = f"{node_id} {object_id}" if node_id else object_id
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

            if discovery_hash in mqtt_data.discovery_pending_discovered:
                pending = mqtt_data.discovery_pending_discovered[discovery_hash][
                    "pending"
                ]
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

        _LOGGER.debug("Process component discovery payload %s", payload)
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
                    MQTT_DISCOVERY_DONE.format(*discovery_hash),
                    discovery_done,
                ),
                "pending": deque([]),
            }

        if component not in mqtt_data.platforms_loaded and payload:
            # Load component first
            async_dispatcher_send(hass, MQTT_DISCOVERY_NEW_COMPONENT, payload)
        elif already_discovered:
            # Dispatch update
            message = f"Component has already been discovered: {component} {discovery_id}, sending update"
            async_log_discovery_origin_info(message, payload, logging.DEBUG)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(*discovery_hash), payload
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
                hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), None
            )

    # async_subscribe will never suspend so there is no need to create a task
    # here and its faster to await them in sequence
    mqtt_data.discovery_unsubscribe = [
        await mqtt.async_subscribe(hass, topic, async_discovery_message_received, 0)
        for topic in (
            f"{discovery_topic}/+/+/config",
            f"{discovery_topic}/+/+/+/config",
        )
    ]

    mqtt_data.last_discovery = time.monotonic()
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

        mqtt_data.integration_unsubscribe.update(
            {
                f"{integration}_{topic}": await mqtt.async_subscribe(
                    hass,
                    topic,
                    functools.partial(async_integration_message_received, integration),
                    0,
                )
                for topic in topics
            }
        )


async def async_stop(hass: HomeAssistant) -> None:
    """Stop MQTT Discovery."""
    mqtt_data = hass.data[DATA_MQTT]
    for unsub in mqtt_data.discovery_unsubscribe:
        unsub()
    mqtt_data.discovery_unsubscribe = []
    for key, unsub in list(mqtt_data.integration_unsubscribe.items()):
        unsub()
        mqtt_data.integration_unsubscribe.pop(key)
