"""Support for MQTT discovery."""

import asyncio
from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import functools
from itertools import chain
import logging
import re
import time
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.config_entries import (
    SOURCE_MQTT,
    ConfigEntry,
    signal_discovered_config_entry_removed,
)
from homeassistant.const import CONF_DEVICE, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HassJobType, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo, ReceivePayloadType
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.loader import async_get_mqtt
from homeassistant.util.json import json_loads_object
from homeassistant.util.signal_type import SignalTypeFormat

from .abbreviations import ABBREVIATIONS, DEVICE_ABBREVIATIONS, ORIGIN_ABBREVIATIONS
from .client import async_publish, async_subscribe_internal
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_AVAILABILITY,
    CONF_CHILD_DEVICE,
    CONF_CHILD_DEVICES,
    CONF_COMPONENTS,
    CONF_CONNECTIONS,
    CONF_DISCOVERY_QOS,
    CONF_IDENTIFIERS,
    CONF_ORIGIN,
    CONF_TOPIC,
    DOMAIN,
    SUPPORTED_COMPONENTS,
)
from .models import (
    DATA_MQTT,
    KeptDevices,
    MqttChildDeviceConfig,
    MqttComponentConfig,
    MqttDiscoveryChildDevice,
    MqttOriginInfo,
    ReceiveMessage,
)
from .schemas import (
    DEVICE_DISCOVERY_SCHEMA,
    MQTT_ORIGIN_INFO_SCHEMA,
    SHARED_OPTIONS,
    validate_device_discovery_components,
)
from .util import (
    async_cleanup_device_registry,
    async_cleanup_removed_component_device,
    async_forward_entry_setup_and_setup_discovery,
)

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
MQTT_DISCOVERY_DONE: SignalTypeFormat[Any] = SignalTypeFormat(
    "mqtt_discovery_done_{}_{}"
)

TOPIC_BASE = "~"

CONF_MIGRATE_DISCOVERY = "migrate_discovery"

MIGRATE_DISCOVERY_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_MIGRATE_DISCOVERY): True},
)


class MQTTDiscoveryPayload(dict[str, Any]):
    """Class to hold and MQTT discovery payload and discovery data."""

    device_discovery: bool = False
    migrate_discovery: bool = False
    # Set when a device discovery payload omits the component
    kept_devices: KeptDevices | None = None
    discovery_data: DiscoveryInfoType


@dataclass(frozen=True, slots=True)
class _DeviceDiscoveryDiff:
    """The known components a device discovery payload removes."""

    desired_components: set[tuple[str, str]]
    desired_child_identifiers: frozenset[str]
    removed_components: set[tuple[str, str]]


@dataclass(frozen=True)
class MQTTIntegrationDiscoveryConfig:
    """Class to hold an integration discovery playload."""

    integration: str
    msg: ReceiveMessage


def clear_discovery_hash(hass: HomeAssistant, discovery_hash: tuple[str, str]) -> None:
    """Clear entry from already discovered list."""
    hass.data[DATA_MQTT].discovery_already_discovered.pop(discovery_hash, None)


def set_discovery_hash(hass: HomeAssistant, discovery_data: DiscoveryInfoType) -> None:
    """Add entry to already discovered list."""
    hass.data[DATA_MQTT].discovery_already_discovered[
        discovery_data[ATTR_DISCOVERY_HASH]
    ] = discovery_data


@callback
def get_origin_log_string(
    discovery_payload: MQTTDiscoveryPayload, *, include_url: bool
) -> str:
    """Get the origin information from a discovery payload for logging."""
    if CONF_ORIGIN not in discovery_payload:
        return ""
    origin_info: MqttOriginInfo = discovery_payload[CONF_ORIGIN]
    log = f" from external application {origin_info['name']}"
    if sw_version := origin_info.get("sw_version"):
        log += f", version: {sw_version}"
    if include_url and (support_url := origin_info.get("support_url")):
        log += f", support URL: {support_url}"
    return log


@callback
def get_origin_support_url(discovery_payload: MQTTDiscoveryPayload) -> str | None:
    """Get the origin information support URL from a discovery payload."""
    if CONF_ORIGIN not in discovery_payload:
        return ""
    origin_info: MqttOriginInfo = discovery_payload[CONF_ORIGIN]
    return origin_info.get("support_url")


@callback
def async_log_discovery_origin_info(
    message: str, discovery_payload: MQTTDiscoveryPayload
) -> None:
    """Log information about the discovery and origin."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "%s%s", message, get_origin_log_string(discovery_payload, include_url=True)
        )


@callback
def _replace_abbreviations(payload: Any, abbreviations: dict[str, str]) -> None:
    """Replace abbreviations in an MQTT discovery payload."""
    if isinstance(payload, dict):
        for key in [key for key in payload if key in abbreviations]:
            payload[abbreviations[key]] = payload.pop(key)


@callback
def _replace_all_abbreviations(
    payload: dict[str, Any], component_only: bool = False
) -> None:
    """Replace all abbreviations in an MQTT discovery payload."""
    _replace_abbreviations(payload, ABBREVIATIONS)
    for availability_conf in probatio.EnsureList()(payload.get(CONF_AVAILABILITY)):
        _replace_abbreviations(availability_conf, ABBREVIATIONS)
    if component_only:
        return
    _replace_abbreviations(payload.get(CONF_ORIGIN), ORIGIN_ABBREVIATIONS)
    _replace_abbreviations(device := payload.get(CONF_DEVICE), DEVICE_ABBREVIATIONS)
    if isinstance(device, dict):
        _replace_abbreviations(device.get(CONF_CHILD_DEVICE), DEVICE_ABBREVIATIONS)
    containers = [payload]
    for child_device in probatio.EnsureList()(payload.get(CONF_CHILD_DEVICES)):
        if isinstance(child_device, dict):
            _replace_abbreviations(child_device, DEVICE_ABBREVIATIONS)
            _replace_abbreviations(child_device, ABBREVIATIONS)
            containers.append(child_device)
    for container in containers:
        if isinstance(components := container.get(CONF_COMPONENTS), dict):
            for component_config in components.values():
                # The schema rejects a component that is not a mapping
                if isinstance(component_config, dict):
                    _replace_all_abbreviations(component_config, component_only=True)


@callback
def _parse_json_payload(
    topic: str, payload: ReceivePayloadType
) -> MQTTDiscoveryPayload | None:
    """Parse a JSON discovery payload, an empty payload is parsed as empty."""
    try:
        return MQTTDiscoveryPayload(json_loads_object(payload) if payload else {})
    except ValueError:
        _LOGGER.warning(
            "Unable to parse JSON discovery payload on topic '%s': '%s'",
            topic,
            payload,
        )
        return None


@callback
def _async_process_discovery_migration(payload: MQTTDiscoveryPayload) -> bool:
    """Process a discovery migration request in the discovery payload."""
    # Allow abbreviation
    if migr_discvry := payload.pop("migr_discvry", None):
        payload[CONF_MIGRATE_DISCOVERY] = migr_discvry
    if CONF_MIGRATE_DISCOVERY not in payload:
        return False
    try:
        MIGRATE_DISCOVERY_SCHEMA(payload)
    except probatio.Invalid as exc:
        _LOGGER.warning(exc)
        return False
    payload.migrate_discovery = True
    payload.clear()
    return True


@callback
def _parse_device_payload(
    hass: HomeAssistant,
    payload: ReceivePayloadType,
    topic: str,
    object_id: str,
    node_id: str | None,
) -> MQTTDiscoveryPayload | None:
    """Parse a device discovery payload.

    An empty payload or a migration request is parsed as an empty payload, which
    removes or migrates all known components of the device.
    """
    if payload == "":
        if _async_get_known_device_components(hass, topic):
            return MQTTDiscoveryPayload()
        _LOGGER.warning(
            "No device components to cleanup for %s, node_id '%s'", object_id, node_id
        )
        return None
    if (
        device_payload := _parse_json_payload(topic, payload)
    ) is None or _async_process_discovery_migration(device_payload):
        return device_payload
    _replace_all_abbreviations(device_payload)
    try:
        validated_payload = validate_device_discovery_components(
            DEVICE_DISCOVERY_SCHEMA(device_payload)
        )
    except probatio.Invalid as exc:
        _LOGGER.warning(
            "Invalid MQTT device discovery payload for %s, %s: '%s'",
            object_id,
            exc,
            payload,
        )
        return None
    # Use the validated devices, the shared and component options are validated
    # with each component
    device_payload[CONF_DEVICE] = validated_payload[CONF_DEVICE]
    if CONF_CHILD_DEVICES in validated_payload:
        device_payload[CONF_CHILD_DEVICES] = validated_payload[CONF_CHILD_DEVICES]
    return device_payload


def _device_discovery_components(
    device_payload: MQTTDiscoveryPayload,
) -> Iterator[tuple[str, dict[str, Any], MqttChildDeviceConfig | None]]:
    """Yield the components of the device and its child devices."""
    for component_id, config in device_payload.get(CONF_COMPONENTS, {}).items():
        yield component_id, config, None
    child_device: MqttDiscoveryChildDevice
    for child_device in device_payload.get(CONF_CHILD_DEVICES, []):
        child_config = MqttChildDeviceConfig(identifiers=child_device["identifiers"])
        if "name" in child_device:
            child_config["name"] = child_device["name"]
        for component_id, config in child_device["components"].items():
            yield component_id, config, child_config


@callback
def _async_known_discovery_data(
    hass: HomeAssistant,
) -> Iterator[tuple[tuple[str, str], DiscoveryInfoType]]:
    """Yield the discovery data of the disabled and the discovered components."""
    mqtt_data = hass.data[DATA_MQTT]
    for discovery_hash, disabled in mqtt_data.discovery_discovered_and_disabled.items():
        yield discovery_hash, disabled.discovery_data
    yield from mqtt_data.discovery_already_discovered.items()


@callback
def _async_get_known_device_components(
    hass: HomeAssistant, topic: str
) -> set[tuple[str, str]]:
    """Return the discovery hashes of the known components of a device topic.

    A pending payload is processed after the payload being processed, which is
    processed after the payload of a discovered component.
    """
    known_components = {
        discovery_hash: discovery_data[ATTR_DISCOVERY_PAYLOAD]
        for discovery_hash, discovery_data in _async_known_discovery_data(hass)
        if discovery_data[ATTR_DISCOVERY_TOPIC] == topic
    }
    pending_discovered = hass.data[DATA_MQTT].discovery_pending_discovered
    for discovery_hash, pending in pending_discovered.items():
        # The pending payloads are queued from new to old
        for payload in (*pending["pending"], pending["processing"]):
            if payload.discovery_data[ATTR_DISCOVERY_TOPIC] == topic:
                known_components[discovery_hash] = payload
                break
    return {discovery_hash for discovery_hash, p in known_components.items() if p}


@callback
def _async_diff_device_discovery(
    hass: HomeAssistant,
    topic: str,
    object_id: str,
    node_id: str | None,
    device_payload: MQTTDiscoveryPayload,
) -> _DeviceDiscoveryDiff:
    """Return the known components a device payload removes.

    The payload is the desired state of the device, a known component is removed
    when it is omitted. A component with only a platform is ignored, a known one
    is kept as is.
    """
    known_components = _async_get_known_device_components(hass, topic)
    desired_components: set[tuple[str, str]] = set()
    child_identifiers: set[str] = set()
    for component_id, config, child_device in _device_discovery_components(
        device_payload
    ):
        discovery_hash = (
            config[CONF_PLATFORM],
            f"{object_id} {node_id} {component_id}"
            if node_id
            else f"{object_id} {component_id}",
        )
        if len(config) > 1:
            child_identifiers.update(
                child_device["identifiers"] if child_device else []
            )
        elif discovery_hash not in known_components:
            continue
        desired_components.add(discovery_hash)
    return _DeviceDiscoveryDiff(
        desired_components,
        frozenset(child_identifiers),
        known_components - desired_components,
    )


@callback
def _async_get_main_device_id(
    hass: HomeAssistant, config_entry_id: str, device_config: Mapping[str, Any]
) -> str | None:
    """Return the ID of the registered main device of a validated device config."""
    device_registry = dr.async_get(hass)
    for identifier in device_config[CONF_IDENTIFIERS]:
        if device := device_registry.async_get_device_by_identifier(
            (DOMAIN, identifier), config_entry_id
        ):
            return device.id
    for connection_type, value in device_config[CONF_CONNECTIONS]:
        # The device registry normalizes the MAC address of the connection
        if device := device_registry.async_get_device_by_connection(
            (connection_type, value), config_entry_id
        ):
            return device.id
    return None


async def async_clear_removed_device_discovery_topic(
    hass: HomeAssistant, config_entry_id: str, device_entry: dr.AnyDeviceEntry
) -> None:
    """Clear the device discovery topic of a device the user removes.

    Clearing the retained payload prevents the device from being discovered again.
    A removed child device keeps the topic, unless its parent device has no
    components left.
    """
    main_device_id = (
        device_entry.parent_device_id
        if isinstance(device_entry, dr.ChildDeviceEntry)
        else device_entry.id
    )
    if (
        discovery_data := next(
            (
                discovery_data
                for _, discovery_data in _async_known_discovery_data(hass)
                if (payload := discovery_data[ATTR_DISCOVERY_PAYLOAD]).device_discovery
                and _async_get_main_device_id(
                    hass, config_entry_id, payload[CONF_DEVICE]
                )
                == main_device_id
            ),
            None,
        )
    ) is None:
        return
    topic: str = discovery_data[ATTR_DISCOVERY_TOPIC]
    if isinstance(device_entry, dr.ChildDeviceEntry):
        device_registry = dr.async_get(hass)
        # Remove the child device first, so its parent device can be cleaned up
        device_registry.async_remove_device(device_entry.id)
        await async_cleanup_device_registry(hass, main_device_id, config_entry_id)
        if device_registry.async_get(main_device_id) is not None:
            application: str = discovery_data[ATTR_DISCOVERY_PAYLOAD][CONF_ORIGIN][
                CONF_NAME
            ]
            _LOGGER.warning(
                "Although child device %s was removed from Home Assistant, it will "
                "be added again when a new MQTT discovery config is received from "
                "%s on topic %s. To prevent this, configure %s to no longer send "
                "this child device",
                device_entry.name or device_entry.id,
                application,
                topic,
                application,
            )
            return
    await async_publish(hass, topic, None, retain=True)


async def async_start(  # noqa: C901
    hass: HomeAssistant, discovery_topic: str, config_entry: ConfigEntry
) -> None:
    """Start MQTT Discovery."""
    mqtt_data = hass.data[DATA_MQTT]
    pending_discovered = mqtt_data.discovery_pending_discovered
    disabled_entities = mqtt_data.discovery_discovered_and_disabled
    platform_setup_lock: dict[str, asyncio.Lock] = {}
    integration_discovery_messages: dict[str, MQTTIntegrationDiscoveryConfig] = {}

    @callback
    def _async_add_component(discovery_payload: MQTTDiscoveryPayload) -> None:
        """Add a component from a discovery message."""
        discovery_hash = discovery_payload.discovery_data[ATTR_DISCOVERY_HASH]
        component, discovery_id = discovery_hash
        disabled = disabled_entities.get(discovery_hash)
        new_topic: str = discovery_payload.discovery_data[ATTR_DISCOVERY_TOPIC]
        if (
            disabled is not None
            and (disabled_topic := disabled.discovery_data[ATTR_DISCOVERY_TOPIC])
            != new_topic
        ):
            if er.async_get(hass).async_get_entity_id(*disabled.registry_key) is None:
                # The disabled entity was removed from the entity registry
                del disabled_entities[discovery_hash]
            else:
                # Like a loaded entity, a disabled entity can only be updated through
                # the topic it was discovered on, until a migration request is
                # received on that topic. Mark the discovery message as handled, so
                # pending discovery messages for this component are processed.
                _LOGGER.warning(
                    "Received a conflicting MQTT discovery message for disabled %s "
                    "'%s' which was previously discovered on topic %s%s; the "
                    "conflicting discovery message was received on topic %s%s; to "
                    "move the component to another discovery topic, publish "
                    '{"migrate_discovery": true} to %s first',
                    component,
                    discovery_id,
                    disabled_topic,
                    get_origin_log_string(
                        disabled.discovery_data[ATTR_DISCOVERY_PAYLOAD],
                        include_url=False,
                    ),
                    new_topic,
                    get_origin_log_string(discovery_payload, include_url=False),
                    disabled_topic,
                )
                async_dispatcher_send(
                    hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), None
                )
                return
        async_log_discovery_origin_info(
            f"Found new component: {component} {discovery_id}", discovery_payload
        )
        mqtt_data.discovery_already_discovered[discovery_hash] = (
            discovery_payload.discovery_data
        )
        async_dispatcher_send(
            hass, MQTT_DISCOVERY_NEW.format(component, "mqtt"), discovery_payload
        )

    async def _async_component_setup(
        component: str, discovery_payload: MQTTDiscoveryPayload
    ) -> None:
        """Perform component set up."""
        async with platform_setup_lock.setdefault(component, asyncio.Lock()):
            if component not in mqtt_data.platforms_loaded:
                await async_forward_entry_setup_and_setup_discovery(
                    hass, config_entry, {component}
                )
        _async_add_component(discovery_payload)

    @callback
    def async_discovery_message_received(msg: ReceiveMessage) -> None:
        """Process the received message."""
        mqtt_data.last_discovery = msg.timestamp
        payload = msg.payload
        topic = msg.topic
        topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)
        if not (match := TOPIC_MATCHER.match(topic_trimmed)):
            if topic_trimmed.endswith("config"):
                _LOGGER.warning(
                    "Received message on illegal discovery topic '%s'. The topic"
                    " contains non allowed characters. For more information see "
                    "https://www.home-assistant.io/integrations/mqtt/#discovery-topic",
                    topic,
                )
            return
        component, node_id, object_id = match.groups()
        discovered_components: list[MqttComponentConfig] = []
        if component == CONF_DEVICE:
            # The payload is the desired state of the device, an empty payload or a
            # migration request removes or migrates all known components
            if (
                device_payload := _parse_device_payload(
                    hass, payload, topic, object_id, node_id
                )
            ) is None:
                return
            diff = _async_diff_device_discovery(
                hass, topic, object_id, node_id, device_payload
            )
            origin_info = get_origin_log_string(device_payload, include_url=False)
            # Without desired components, the removals clean up all devices left
            # empty. The removals are done first, so a renamed component can keep
            # its unique ID.
            kept_devices = (
                KeptDevices(
                    _async_get_main_device_id(
                        hass, config_entry.entry_id, device_payload[CONF_DEVICE]
                    ),
                    diff.desired_child_identifiers,
                )
                if diff.desired_components
                else None
            )
            for removed_component, discovery_id in diff.removed_components:
                if device_payload:
                    _LOGGER.warning(
                        "Removing %s '%s', omitted from the MQTT device discovery "
                        "payload on topic %s%s",
                        removed_component,
                        discovery_id,
                        topic,
                        origin_info,
                    )
                removal_payload = MQTTDiscoveryPayload()
                removal_payload.device_discovery = True
                removal_payload.migrate_discovery = device_payload.migrate_discovery
                removal_payload.kept_devices = kept_devices
                discovered_components.append(
                    MqttComponentConfig(
                        removed_component,
                        discovery_id.partition(" ")[2],
                        object_id,
                        removal_payload,
                    )
                )
            for component_id, config, child_device in _device_discovery_components(
                device_payload
            ):
                component = config.pop(CONF_PLATFORM)
                # The object_id of the topic is the node_id of the component, a
                # node_id of the topic is added to the component_id as object_id
                component_object_id = (
                    f"{node_id} {component_id}" if node_id else component_id
                )
                if not config:
                    # Removing a component with only a platform is deprecated, the
                    # log can be removed in HA Core 2027.12, the skip must stay
                    _LOGGER.info(
                        "Ignoring %s '%s' with only the platform option in the MQTT "
                        "device discovery payload on topic %s%s; removing a "
                        "component this way is deprecated, omit it from the "
                        "payload instead",
                        component,
                        f"{object_id} {component_object_id}",
                        topic,
                        origin_info,
                    )
                    continue
                discovery_payload = MQTTDiscoveryPayload(config)
                # All components share the device config, so a component of a
                # child device gets a new dict with its child device
                discovery_payload[CONF_DEVICE] = (
                    device_payload[CONF_DEVICE]
                    if child_device is None
                    else {
                        **device_payload[CONF_DEVICE],
                        CONF_CHILD_DEVICE: child_device,
                    }
                )
                discovery_payload[CONF_ORIGIN] = device_payload.get(CONF_ORIGIN)
                # A shared option is inherited, unless the component sets it
                for option in SHARED_OPTIONS:
                    if option in device_payload and option not in discovery_payload:
                        discovery_payload[option] = device_payload[option]
                discovery_payload.device_discovery = True
                discovered_components.append(
                    MqttComponentConfig(
                        component, component_object_id, object_id, discovery_payload
                    )
                )
            _LOGGER.debug("Process device discovery payload %s", device_payload)
            device_discovery_id = f"{node_id} {object_id}" if node_id else object_id
            async_log_discovery_origin_info(
                f"Processing device discovery for '{device_discovery_id}'",
                device_payload,
            )
        else:
            if (component_payload := _parse_json_payload(topic, payload)) is None:
                return
            if not _async_process_discovery_migration(component_payload):
                _replace_all_abbreviations(component_payload)
                if CONF_ORIGIN in component_payload:
                    try:
                        MQTT_ORIGIN_INFO_SCHEMA(component_payload[CONF_ORIGIN])
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.warning(
                            "Unable to parse origin information from discovery "
                            "message: %s, got %s",
                            exc,
                            component_payload[CONF_ORIGIN],
                        )
                        return
            discovered_components.append(
                MqttComponentConfig(component, object_id, node_id, component_payload)
            )

        for component_config in discovered_components:
            discovery_payload = component_config.discovery_payload
            if TOPIC_BASE in discovery_payload:
                base = discovery_payload.pop(TOPIC_BASE)
                availability = probatio.EnsureList()(
                    discovery_payload.get(CONF_AVAILABILITY)
                )
                for topic_config, key in chain(
                    ((discovery_payload, key) for key in discovery_payload),
                    ((conf, CONF_TOPIC) for conf in availability),
                ):
                    if (
                        isinstance(topic_config, dict)
                        and key.endswith("topic")
                        and isinstance(value := topic_config.get(key), str)
                        and value
                    ):
                        if value[0] == TOPIC_BASE:
                            topic_config[key] = f"{base}{value[1:]}"
                        if value[-1] == TOPIC_BASE:
                            topic_config[key] = f"{value[:-1]}{base}"
            # If present, the node_id will be included in the discovery_id
            discovery_id = (
                f"{component_config.node_id} {component_config.object_id}"
                if component_config.node_id
                else component_config.object_id
            )
            discovery_hash = (component_config.component, discovery_id)
            # Attach MQTT topic to the payload, used for debug prints
            discovery_payload.discovery_data = {
                ATTR_DISCOVERY_HASH: discovery_hash,
                ATTR_DISCOVERY_PAYLOAD: discovery_payload,
                ATTR_DISCOVERY_TOPIC: topic,
            }
            if discovery_hash in pending_discovered:
                pending_discovered[discovery_hash]["pending"].appendleft(
                    discovery_payload
                )
                _LOGGER.debug(
                    "Component has already been discovered: %s %s, queuing update",
                    *discovery_hash,
                )
                continue
            async_process_discovery_payload(*discovery_hash, discovery_payload)

    @callback
    def async_process_discovery_payload(
        component: str, discovery_id: str, payload: MQTTDiscoveryPayload
    ) -> None:
        """Process the payload of a new discovery."""
        _LOGGER.debug("Process component discovery payload %s", payload)
        discovery_hash = (component, discovery_id)
        already_discovered = discovery_hash in mqtt_data.discovery_already_discovered
        if (already_discovered or payload) and discovery_hash not in pending_discovered:

            @callback
            def discovery_done(_: Any) -> None:
                pending = pending_discovered[discovery_hash]["pending"]
                _LOGGER.debug("Pending discovery for %s: %s", discovery_hash, pending)
                if not pending:
                    pending_discovered.pop(discovery_hash)["unsub"]()
                    return
                payload = pending.pop()
                pending_discovered[discovery_hash]["processing"] = payload
                async_process_discovery_payload(component, discovery_id, payload)

            pending_discovered[discovery_hash] = {
                "unsub": async_dispatcher_connect(
                    hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), discovery_done
                ),
                "pending": deque(),
                "processing": payload,
            }

        if component not in mqtt_data.platforms_loaded and payload:
            config_entry.async_create_task(
                hass, _async_component_setup(component, payload)
            )
            return
        if already_discovered:
            async_log_discovery_origin_info(
                f"Component has already been discovered: {component} {discovery_id}, "
                "sending update",
                payload,
            )
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(*discovery_hash), payload
            )
            return
        if payload:
            _async_add_component(payload)
            return
        # A disabled entity is bound to the topic it was discovered on. A migration
        # request on that topic stops the tracking, so the entity can be discovered
        # on the topic it is migrated to. An empty payload also removes the entity.
        if (disabled := disabled_entities.get(discovery_hash)) is not None:
            disabled_payload: MQTTDiscoveryPayload = disabled.discovery_data[
                ATTR_DISCOVERY_PAYLOAD
            ]
            disabled_topic: str = disabled.discovery_data[ATTR_DISCOVERY_TOPIC]
            removal_topic: str = payload.discovery_data[ATTR_DISCOVERY_TOPIC]
            if disabled_topic != removal_topic and not payload.migrate_discovery:
                # A device discovery payload only removes the components of its
                # own topic, and removing the entity clears the retained discovery
                # topic, which would remove all other components of the device too
                _LOGGER.warning(
                    "Ignoring empty MQTT discovery payload for disabled %s '%s' "
                    "received on topic %s, the component was discovered on topic "
                    "%s%s; after migration to device discovery, a component cannot "
                    "be removed by publishing an empty payload to its old single "
                    "component discovery topic; to remove the component, omit it "
                    "from the device discovery payload published to %s",
                    component,
                    discovery_id,
                    removal_topic,
                    disabled_topic,
                    get_origin_log_string(disabled_payload, include_url=False),
                    disabled_topic,
                )
            elif disabled_topic == removal_topic and payload.migrate_discovery:
                del disabled_entities[discovery_hash]
            elif disabled_topic == removal_topic:
                del disabled_entities[discovery_hash]
                # Without the registry hook, removing the entity does not publish
                # an empty payload to the device discovery topic, which would
                # remove the whole device
                if disabled_payload.device_discovery and (
                    remove_hook := mqtt_data.discovery_registry_hooks.pop(
                        discovery_hash, None
                    )
                ):
                    remove_hook()
                entity_registry = er.async_get(hass)
                if (
                    entity_id := entity_registry.entities.get_entity_id(
                        disabled.registry_key
                    )
                ) and (entity_entry := entity_registry.async_get(entity_id)):
                    entity_registry.async_remove(entity_id)
                    hass.async_create_task(
                        async_cleanup_removed_component_device(
                            hass,
                            entity_entry.device_id,
                            entity_entry.config_entry_id,
                            payload.kept_devices,
                        ),
                        name=f"Check for cleanup device registry for {entity_id}",
                    )
        async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), None)

    discovery_qos: int = config_entry.options.get(CONF_DISCOVERY_QOS, 0)
    # Subscribe to the component discovery topics before the device discovery topics
    mqtt_data.discovery_unsubscribe = [
        async_subscribe_internal(
            hass,
            topic,
            async_discovery_message_received,
            discovery_qos,
            job_type=HassJobType.Callback,
        )
        for topic in (
            *(f"{discovery_topic}/{comp}/+/config" for comp in SUPPORTED_COMPONENTS),
            *(f"{discovery_topic}/{comp}/+/+/config" for comp in SUPPORTED_COMPONENTS),
            f"{discovery_topic}/device/+/config",
            f"{discovery_topic}/device/+/+/config",
        )
    ]

    mqtt_data.last_discovery = time.monotonic()
    mqtt_integrations = await async_get_mqtt(hass)

    async def _async_handle_config_entry_removed(entry: ConfigEntry) -> None:
        """Rediscover the discovery messages of a removed config entry."""
        for discovery_key in entry.discovery_keys[DOMAIN]:
            if (
                discovery_key.version == 1
                and isinstance(topic := discovery_key.key, str)
                and (message := integration_discovery_messages.pop(topic, None))
            ):
                _LOGGER.debug("Rediscover service on topic %s", topic)
                await async_integration_message_received(
                    message.integration, message.msg
                )

    mqtt_data.discovery_unsubscribe.append(
        async_dispatcher_connect(
            hass,
            signal_discovered_config_entry_removed(DOMAIN),
            _async_handle_config_entry_removed,
        )
    )

    async def async_integration_message_received(
        integration: str, msg: ReceiveMessage
    ) -> None:
        """Process the received message."""
        if (
            known := integration_discovery_messages.get(msg.topic)
        ) and known.msg.payload == msg.payload:
            _LOGGER.debug(
                "Ignoring already processed discovery message for '%s' on topic %s: %s",
                integration,
                msg.topic,
                msg.payload,
            )
            return
        if TYPE_CHECKING:
            assert mqtt_data.data_config_flow_lock
        # The lock is not intended to prevent a race, it prevents initiating many
        # parallel config flows for performance
        async with mqtt_data.data_config_flow_lock:
            discovery_flow.async_create_flow(
                hass,
                integration,
                {"source": SOURCE_MQTT},
                MqttServiceInfo(
                    topic=msg.topic,
                    payload=msg.payload,
                    qos=msg.qos,
                    retain=msg.retain,
                    subscribed_topic=msg.subscribed_topic,
                    timestamp=msg.timestamp,
                ),
                discovery_key=discovery_flow.DiscoveryKey(
                    domain=DOMAIN, key=msg.topic, version=1
                ),
            )
            if msg.payload:
                integration_discovery_messages[msg.topic] = (
                    MQTTIntegrationDiscoveryConfig(integration=integration, msg=msg)
                )
            else:
                integration_discovery_messages.pop(msg.topic, None)

    mqtt_data.integration_unsubscribe.update(
        {
            f"{integration}_{topic}": async_subscribe_internal(
                hass,
                topic,
                functools.partial(async_integration_message_received, integration),
                discovery_qos,
                job_type=HassJobType.Coroutinefunction,
            )
            for integration, topics in mqtt_integrations.items()
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
