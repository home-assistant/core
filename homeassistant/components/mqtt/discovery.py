"""Support for MQTT discovery."""

import asyncio
from collections import deque
from collections.abc import Mapping
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
from homeassistant.const import CONF_DEVICE, CONF_PLATFORM
from homeassistant.core import HassJobType, HomeAssistant, callback
from homeassistant.helpers import discovery_flow, entity_registry as er
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
from .client import async_subscribe_internal
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
    DiscoveredDisabledEntity,
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
    async_forward_entry_setup_and_setup_discovery,
)

ABBREVIATIONS_SET = set(ABBREVIATIONS)
DEVICE_ABBREVIATIONS_SET = set(DEVICE_ABBREVIATIONS)
ORIGIN_ABBREVIATIONS_SET = set(ORIGIN_ABBREVIATIONS)

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
    # A component omitted from a device discovery payload only cleans up its device
    # when the payload omits its child device too, the parent device is kept
    cleanup_device: bool = True
    cleanup_parent_device: bool = True
    discovery_data: DiscoveryInfoType


@dataclass(frozen=True, slots=True)
class _DeviceDiscoveryComponent:
    """A component of a device discovery payload."""

    component_id: str
    config: dict[str, Any]
    child_device: MqttChildDeviceConfig | None = None


@dataclass(frozen=True, slots=True)
class _DeviceDiscoveryDiff:
    """The known components and child devices a device discovery payload removes."""

    desired_components: set[tuple[str, str]]
    removed_components: dict[tuple[str, str], MQTTDiscoveryPayload]
    removed_child_devices: set[frozenset[str]]


@dataclass(frozen=True)
class MQTTIntegrationDiscoveryConfig:
    """Class to hold an integration discovery playload."""

    integration: str
    msg: ReceiveMessage


@callback
def _async_process_discovery_migration(payload: MQTTDiscoveryPayload) -> bool:
    """Process a discovery migration request in the discovery payload."""
    # Allow abbreviation
    if migr_discvry := (payload.pop("migr_discvry", None)):
        payload[CONF_MIGRATE_DISCOVERY] = migr_discvry
    if CONF_MIGRATE_DISCOVERY in payload:
        try:
            MIGRATE_DISCOVERY_SCHEMA(payload)
        except probatio.Invalid as exc:
            _LOGGER.warning(exc)
            return False
        payload.migrate_discovery = True
        payload.clear()
        return True
    return False


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
    sw_version_log = ""
    if sw_version := origin_info.get("sw_version"):
        sw_version_log = f", version: {sw_version}"
    support_url_log = ""
    if include_url and (support_url := get_origin_support_url(discovery_payload)):
        support_url_log = f", support URL: {support_url}"
    return (
        " from external application "
        f"{origin_info['name']}{sw_version_log}{support_url_log}"
    )


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
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        # bail out early if debug logging is disabled
        return
    _LOGGER.debug(
        "%s%s", message, get_origin_log_string(discovery_payload, include_url=True)
    )


@callback
def _replace_abbreviations(
    payload: dict[str, Any] | str,
    abbreviations: dict[str, str],
    abbreviations_set: set[str],
) -> None:
    """Replace abbreviations in an MQTT discovery payload."""
    if not isinstance(payload, dict):
        return
    for key in abbreviations_set.intersection(payload):
        payload[abbreviations[key]] = payload.pop(key)


@callback
def _replace_all_abbreviations(
    discovery_payload: dict[str, Any], component_only: bool = False
) -> None:
    """Replace all abbreviations in an MQTT discovery payload."""

    _replace_abbreviations(discovery_payload, ABBREVIATIONS, ABBREVIATIONS_SET)

    if CONF_AVAILABILITY in discovery_payload:
        for availability_conf in probatio.EnsureList()(
            discovery_payload[CONF_AVAILABILITY]
        ):
            _replace_abbreviations(availability_conf, ABBREVIATIONS, ABBREVIATIONS_SET)

    if component_only:
        return

    if CONF_ORIGIN in discovery_payload:
        _replace_abbreviations(
            discovery_payload[CONF_ORIGIN],
            ORIGIN_ABBREVIATIONS,
            ORIGIN_ABBREVIATIONS_SET,
        )

    if CONF_DEVICE in discovery_payload:
        device = discovery_payload[CONF_DEVICE]
        _replace_abbreviations(device, DEVICE_ABBREVIATIONS, DEVICE_ABBREVIATIONS_SET)
        if isinstance(device, dict) and CONF_CHILD_DEVICE in device:
            _replace_abbreviations(
                device[CONF_CHILD_DEVICE],
                DEVICE_ABBREVIATIONS,
                DEVICE_ABBREVIATIONS_SET,
            )

    for child_device in probatio.EnsureList()(
        discovery_payload.get(CONF_CHILD_DEVICES)
    ):
        if not isinstance(child_device, dict):
            continue
        _replace_abbreviations(
            child_device, DEVICE_ABBREVIATIONS, DEVICE_ABBREVIATIONS_SET
        )
        _replace_abbreviations(child_device, ABBREVIATIONS, ABBREVIATIONS_SET)
        _replace_component_abbreviations(child_device)

    _replace_component_abbreviations(discovery_payload)


@callback
def _replace_component_abbreviations(payload: dict[str, Any]) -> None:
    """Replace the abbreviations in the components of a device discovery payload."""
    if not isinstance(components := payload.get(CONF_COMPONENTS), dict):
        return
    for comp_conf in components.values():
        # The schema rejects a component that is not a mapping
        if isinstance(comp_conf, dict):
            _replace_all_abbreviations(comp_conf, component_only=True)


@callback
def _replace_topic_base(discovery_payload: MQTTDiscoveryPayload) -> None:
    """Replace topic base in MQTT discovery data."""
    base = discovery_payload.pop(TOPIC_BASE)
    for key, value in discovery_payload.items():
        if isinstance(value, str) and value:
            if value[0] == TOPIC_BASE and key.endswith("topic"):
                discovery_payload[key] = f"{base}{value[1:]}"
            if value[-1] == TOPIC_BASE and key.endswith("topic"):
                discovery_payload[key] = f"{value[:-1]}{base}"
    if discovery_payload.get(CONF_AVAILABILITY):
        for availability_conf in probatio.EnsureList()(
            discovery_payload[CONF_AVAILABILITY]
        ):
            if not isinstance(availability_conf, dict):
                continue
            if topic := str(availability_conf.get(CONF_TOPIC)):
                if topic[0] == TOPIC_BASE:
                    availability_conf[CONF_TOPIC] = f"{base}{topic[1:]}"
                if topic[-1] == TOPIC_BASE:
                    availability_conf[CONF_TOPIC] = f"{topic[:-1]}{base}"


@callback
def _generate_device_config(
    hass: HomeAssistant,
    topic: str,
    object_id: str,
    node_id: str | None,
    migrate_discovery: bool = False,
) -> MQTTDiscoveryPayload:
    """Generate a cleanup or discovery migration message on device cleanup.

    If an empty payload, or a migrate discovery request is received for a device,
    we forward an empty payload for all known components of the device,
    including discovered disabled components.
    """
    component_id_prefix = _device_component_discovery_id(object_id, node_id, "")
    config = MQTTDiscoveryPayload(
        {
            CONF_DEVICE: {},
            CONF_COMPONENTS: {
                discovery_id.removeprefix(component_id_prefix): {
                    CONF_PLATFORM: platform
                }
                for platform, discovery_id in _async_get_known_device_components(
                    hass, topic
                )
            },
        }
    )
    config.migrate_discovery = migrate_discovery
    return config if config[CONF_COMPONENTS] else MQTTDiscoveryPayload({})


@callback
def _parse_device_payload(
    hass: HomeAssistant,
    payload: ReceivePayloadType,
    topic: str,
    object_id: str,
    node_id: str | None,
) -> MQTTDiscoveryPayload:
    """Parse a device discovery payload.

    The device discovery payload is translated info the config payloads for every single
    component inside the device based configuration.
    An empty payload is translated in a cleanup, which forwards an empty payload to all
    removed components.
    """
    device_payload = MQTTDiscoveryPayload()
    if payload == "":
        if not (
            device_payload := _generate_device_config(hass, topic, object_id, node_id)
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
        _LOGGER.warning(
            "Unable to parse JSON discovery payload on topic '%s': '%s'",
            topic,
            payload,
        )
        return device_payload
    if _async_process_discovery_migration(device_payload):
        return _generate_device_config(
            hass, topic, object_id, node_id, migrate_discovery=True
        )
    _replace_all_abbreviations(device_payload)
    try:
        validate_device_discovery_components(DEVICE_DISCOVERY_SCHEMA(device_payload))
    except probatio.Invalid as exc:
        _LOGGER.warning(
            "Invalid MQTT device discovery payload for %s, %s: '%s'",
            object_id,
            exc,
            payload,
        )
        return MQTTDiscoveryPayload({})
    return device_payload


def _device_component_discovery_id(
    object_id: str, node_id: str | None, component_id: str
) -> str:
    """Return the discovery ID of a component of a device discovery payload."""
    return (
        f"{object_id} {node_id} {component_id}"
        if node_id
        else f"{object_id} {component_id}"
    )


def _device_discovery_components(
    device_payload: MQTTDiscoveryPayload,
) -> list[_DeviceDiscoveryComponent]:
    """Return the components of the device and its child devices."""
    device_components = [
        _DeviceDiscoveryComponent(component_id, config)
        for component_id, config in device_payload.get(CONF_COMPONENTS, {}).items()
    ]
    child_device: MqttDiscoveryChildDevice
    for child_device in device_payload.get(CONF_CHILD_DEVICES, []):
        child_device_config = MqttChildDeviceConfig(
            identifiers=child_device["identifiers"]
        )
        if "name" in child_device:
            child_device_config["name"] = child_device["name"]
        device_components.extend(
            _DeviceDiscoveryComponent(component_id, config, child_device_config)
            for component_id, config in child_device["components"].items()
        )
    return device_components


def _child_device_identifiers(
    child_device: Mapping[str, Any] | None,
) -> frozenset[str]:
    """Return the identifiers of a child device, as strings like the schema."""
    if child_device is None:
        return frozenset()
    return frozenset(
        str(identifier)
        for identifier in probatio.EnsureList()(child_device[CONF_IDENTIFIERS])
    )


def _device_keys(device_config: Mapping[str, Any]) -> set[tuple[str, ...]]:
    """Return the identifiers and connections that link a device config."""
    return {
        (CONF_IDENTIFIERS, str(identifier))
        for identifier in probatio.EnsureList()(device_config.get(CONF_IDENTIFIERS))
    } | {
        (CONF_CONNECTIONS, *map(str, connection))
        for connection in device_config.get(CONF_CONNECTIONS, [])
    }


@callback
def _async_get_known_device_components(
    hass: HomeAssistant, topic: str
) -> dict[tuple[str, str], MQTTDiscoveryPayload]:
    """Return the payloads of the known components of a device discovery topic.

    A pending payload is processed after the payload being processed, which is
    processed after the payload of a discovered component.
    """
    mqtt_data = hass.data[DATA_MQTT]
    known_components: dict[tuple[str, str], MQTTDiscoveryPayload] = {}
    for discovery_hash, discovery_data in chain(
        (
            (discovery_hash, disabled_entity.discovery_data)
            for discovery_hash, disabled_entity in (
                mqtt_data.discovery_discovered_and_disabled.items()
            )
        ),
        mqtt_data.discovery_already_discovered.items(),
    ):
        if discovery_data[ATTR_DISCOVERY_TOPIC] == topic:
            known_components[discovery_hash] = discovery_data[ATTR_DISCOVERY_PAYLOAD]
    for (
        discovery_hash,
        pending_discovered,
    ) in mqtt_data.discovery_pending_discovered.items():
        # The pending payloads are queued from new to old
        for payload in chain(
            pending_discovered["pending"], (pending_discovered["processing"],)
        ):
            if payload.discovery_data[ATTR_DISCOVERY_TOPIC] == topic:
                known_components[discovery_hash] = payload
                break
    return {
        discovery_hash: payload
        for discovery_hash, payload in known_components.items()
        if payload
    }


@callback
def _async_diff_device_discovery(
    hass: HomeAssistant,
    topic: str,
    object_id: str,
    node_id: str | None,
    device_payload: MQTTDiscoveryPayload,
) -> _DeviceDiscoveryDiff:
    """Return the known components and child devices a device payload removes.

    The payload is the desired state of the device, a known component is removed
    when it is omitted. A component with only a platform is ignored, a known one
    is kept as is. A known child device is removed when none of its identifiers is
    in a child device with desired components.
    """
    known_components = _async_get_known_device_components(hass, topic)
    desired_components: set[tuple[str, str]] = set()
    desired_child_identifiers: set[str] = set()
    child_device: Mapping[str, Any] | None
    for device_component in _device_discovery_components(device_payload):
        discovery_hash = (
            device_component.config[CONF_PLATFORM],
            _device_component_discovery_id(
                object_id, node_id, device_component.component_id
            ),
        )
        if len(device_component.config) > 1:
            child_device = device_component.child_device
        elif (known_payload := known_components.get(discovery_hash)) is not None:
            child_device = known_payload[CONF_DEVICE].get(CONF_CHILD_DEVICE)
        else:
            continue
        desired_components.add(discovery_hash)
        desired_child_identifiers.update(_child_device_identifiers(child_device))
    return _DeviceDiscoveryDiff(
        desired_components,
        {
            discovery_hash: payload
            for discovery_hash, payload in known_components.items()
            if discovery_hash not in desired_components
        },
        {
            identifiers
            for payload in known_components.values()
            if (
                identifiers := _child_device_identifiers(
                    payload[CONF_DEVICE].get(CONF_CHILD_DEVICE)
                )
            )
            and identifiers.isdisjoint(desired_child_identifiers)
        },
    )


@callback
def _async_remove_omitted_device_components(
    topic: str,
    object_id: str,
    device_payload: MQTTDiscoveryPayload,
    diff: _DeviceDiscoveryDiff,
    discovered_components: list[MqttComponentConfig],
) -> None:
    """Add the removal of the components a device discovery payload omits.

    The removals are done first, so a renamed component can keep its unique ID.
    They only clean up the omitted child devices, so a device that is kept is never
    removed and created again while the components are processed. Without
    components in the payload, or when the payload has another parent device, the
    removals clean up all devices left empty.
    """
    origin_info = get_origin_log_string(device_payload, include_url=False)
    parent_device_keys = _device_keys(device_payload[CONF_DEVICE])
    for identifiers in diff.removed_child_devices:
        _LOGGER.warning(
            "Removing child device %s, omitted from the MQTT device discovery "
            "payload on topic %s%s",
            ", ".join(sorted(identifiers)),
            topic,
            origin_info,
        )
    removals: list[MqttComponentConfig] = []
    for discovery_hash, known_payload in diff.removed_components.items():
        _LOGGER.warning(
            "Removing %s '%s', omitted from the MQTT device discovery payload "
            "on topic %s%s",
            discovery_hash[0],
            discovery_hash[1],
            topic,
            origin_info,
        )
        removal_payload = MQTTDiscoveryPayload()
        removal_payload.device_discovery = True
        if diff.desired_components and not parent_device_keys.isdisjoint(
            _device_keys(known_payload[CONF_DEVICE])
        ):
            removal_payload.cleanup_device = (
                _child_device_identifiers(
                    known_payload[CONF_DEVICE].get(CONF_CHILD_DEVICE)
                )
                in diff.removed_child_devices
            )
            removal_payload.cleanup_parent_device = False
        removals.append(
            MqttComponentConfig(
                discovery_hash[0],
                discovery_hash[1].partition(" ")[2],
                object_id,
                removal_payload,
            )
        )
    discovered_components[:0] = removals


@callback
def _valid_origin_info(discovery_payload: MQTTDiscoveryPayload) -> bool:
    """Parse and validate origin info from a single component discovery payload."""
    if CONF_ORIGIN not in discovery_payload:
        return True
    try:
        MQTT_ORIGIN_INFO_SCHEMA(discovery_payload[CONF_ORIGIN])
    except Exception as exc:  # noqa:BLE001
        _LOGGER.warning(
            "Unable to parse origin information from discovery message: %s, got %s",
            exc,
            discovery_payload[CONF_ORIGIN],
        )
        return False
    return True


@callback
def _merge_common_device_options(
    component_config: MQTTDiscoveryPayload, device_config: dict[str, Any]
) -> None:
    """Merge common device options with the component config options.

    Common options are:
        CONF_AVAILABILITY,
        CONF_AVAILABILITY_MODE,
        CONF_AVAILABILITY_TEMPLATE,
        CONF_AVAILABILITY_TOPIC,
        CONF_COMMAND_TOPIC,
        CONF_ENCODING,
        CONF_PAYLOAD_AVAILABLE,
        CONF_PAYLOAD_NOT_AVAILABLE,
        CONF_STATE_TOPIC,
        CONF_QOS
    Common options in the body of the device based config are inherited into
    the component. Unless the option is explicitly specified at component level,
    in that case the option at component level will override the common option.
    """
    for option in SHARED_OPTIONS:
        if option in device_config and option not in component_config:
            component_config[option] = device_config.get(option)


@callback
def _async_is_conflicting_disabled_entity(
    hass: HomeAssistant, discovery_hash: tuple[str, str], payload: MQTTDiscoveryPayload
) -> bool:
    """Return True if a payload conflicts with a discovered disabled entity.

    Like a loaded entity, a disabled entity can only be updated through the topic
    it was discovered on, until a discovery migration request is received on that
    topic.
    """
    mqtt_data = hass.data[DATA_MQTT]
    if (
        disabled_entity := mqtt_data.discovery_discovered_and_disabled.get(
            discovery_hash
        )
    ) is None:
        return False
    discovery_data = disabled_entity.discovery_data
    discovery_topic: str = discovery_data[ATTR_DISCOVERY_TOPIC]
    new_discovery_topic: str = payload.discovery_data[ATTR_DISCOVERY_TOPIC]
    if discovery_topic == new_discovery_topic:
        return False
    if er.async_get(hass).async_get_entity_id(*disabled_entity.registry_key) is None:
        # The disabled entity was removed from the entity registry
        del mqtt_data.discovery_discovered_and_disabled[discovery_hash]
        return False
    _LOGGER.warning(
        "Received a conflicting MQTT discovery message for disabled %s '%s' which "
        "was previously discovered on topic %s%s; the conflicting discovery message "
        "was received on topic %s%s; to move the component to another discovery "
        'topic, publish {"migrate_discovery": true} to %s first',
        discovery_hash[0],
        discovery_hash[1],
        discovery_topic,
        get_origin_log_string(
            discovery_data[ATTR_DISCOVERY_PAYLOAD], include_url=False
        ),
        new_discovery_topic,
        get_origin_log_string(payload, include_url=False),
        discovery_topic,
    )
    return True


@callback
def _async_untrack_disabled_entity_on_migration(
    hass: HomeAssistant, discovery_hash: tuple[str, str], payload: MQTTDiscoveryPayload
) -> None:
    """Stop tracking a disabled entity when a discovery migration request is received.

    A disabled entity is tracked to bind it to the topic it was discovered on.
    A migration request on that topic removes the tracking, so the entity can be
    discovered on the topic it is migrated to. A disabled entity is not loaded,
    so there is nothing to unload.
    """
    mqtt_data = hass.data[DATA_MQTT]
    if (
        disabled_entity := mqtt_data.discovery_discovered_and_disabled.get(
            discovery_hash
        )
    ) is not None and disabled_entity.discovery_data[
        ATTR_DISCOVERY_TOPIC
    ] == payload.discovery_data[ATTR_DISCOVERY_TOPIC]:
        del mqtt_data.discovery_discovered_and_disabled[discovery_hash]


@callback
def _async_cleanup_disabled_entity(
    hass: HomeAssistant,
    discovery_hash: tuple[str, str],
    disabled_entity: DiscoveredDisabledEntity,
    payload: MQTTDiscoveryPayload,
) -> None:
    """Remove a discovered disabled entity and clean up its device."""
    mqtt_data = hass.data[DATA_MQTT]
    discovery_data = disabled_entity.discovery_data
    discovery_payload: MQTTDiscoveryPayload = discovery_data[ATTR_DISCOVERY_PAYLOAD]
    discovery_topic: str = discovery_data[ATTR_DISCOVERY_TOPIC]
    removal_topic: str = payload.discovery_data[ATTR_DISCOVERY_TOPIC]
    if discovery_topic != removal_topic:
        # Only a component of device discovery is removed through another topic, as
        # a device discovery payload only removes the components of its own topic.
        # Removing the entity clears its retained discovery topic, which would
        # remove all other components of the device too.
        _LOGGER.warning(
            "Ignoring empty MQTT discovery payload for disabled %s '%s' received "
            "on topic %s, the component was discovered on topic %s%s; after "
            "migration to device discovery, a component cannot be removed by "
            "publishing an empty payload to its old single component discovery "
            "topic; to remove the component, omit it from the device discovery "
            "payload published to %s",
            discovery_hash[0],
            discovery_hash[1],
            removal_topic,
            discovery_topic,
            get_origin_log_string(discovery_payload, include_url=False),
            discovery_topic,
        )
        return

    del mqtt_data.discovery_discovered_and_disabled[discovery_hash]
    # Remove the registry hook, so removing the entity from the entity registry
    # below does not publish an empty payload to the device discovery topic,
    # which would remove all components of the device
    if discovery_payload.device_discovery and (
        remove_registry_hook := mqtt_data.discovery_registry_hooks.pop(
            discovery_hash, None
        )
    ):
        remove_registry_hook()
    entity_registry = er.async_get(hass)
    if (
        entity_id := entity_registry.entities.get_entity_id(
            disabled_entity.registry_key
        )
    ) and (entity_entry := entity_registry.async_get(entity_id)):
        entity_registry.async_remove(entity_id)
        if not payload.cleanup_device:
            return
        hass.async_create_task(
            async_cleanup_device_registry(
                hass,
                device_id=entity_entry.device_id,
                config_entry_id=entity_entry.config_entry_id,
                cleanup_parent_device=payload.cleanup_parent_device,
            ),
            name=f"Check for cleanup device registry for {entity_id}",
        )


async def async_start(  # noqa: C901
    hass: HomeAssistant, discovery_topic: str, config_entry: ConfigEntry
) -> None:
    """Start MQTT Discovery."""
    mqtt_data = hass.data[DATA_MQTT]
    platform_setup_lock: dict[str, asyncio.Lock] = {}
    integration_discovery_messages: dict[str, MQTTIntegrationDiscoveryConfig] = {}

    @callback
    def _async_add_component(discovery_payload: MQTTDiscoveryPayload) -> None:
        """Add a component from a discovery message."""
        discovery_hash = discovery_payload.discovery_data[ATTR_DISCOVERY_HASH]
        # A disabled entity is bound to the topic it was discovered on, ignore a
        # config for it received on another topic, but mark the discovery message
        # as handled, so pending discovery messages for this component are processed
        if _async_is_conflicting_disabled_entity(
            hass, discovery_hash, discovery_payload
        ):
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), None
            )
            return
        component, discovery_id = discovery_hash
        message = f"Found new component: {component} {discovery_id}"
        async_log_discovery_origin_info(message, discovery_payload)
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
                    (
                        "Received message on illegal discovery topic '%s'. The topic"
                        " contains non allowed characters. For more information see "
                        "https://www.home-assistant.io/integrations/mqtt/#discovery-topic"
                    ),
                    topic,
                )
            return

        component, node_id, object_id = match.groups()

        discovered_components: list[MqttComponentConfig] = []
        if component == CONF_DEVICE:
            # Process device based discovery message. An empty payload or a
            # migration request is translated into a cleanup or migration payload
            # for every known component of the device. Otherwise the payload is the
            # desired state, and the known components it omits are removed.
            device_discovery_payload = _parse_device_payload(
                hass, payload, topic, object_id, node_id
            )
            if not device_discovery_payload:
                return
            device_discovery_diff: _DeviceDiscoveryDiff | None = None
            if payload and not device_discovery_payload.migrate_discovery:
                device_discovery_diff = _async_diff_device_discovery(
                    hass, topic, object_id, node_id, device_discovery_payload
                )
            device_config: dict[str, Any] = device_discovery_payload[CONF_DEVICE]
            origin_config: dict[str, Any] | None = device_discovery_payload.get(
                CONF_ORIGIN
            )
            for device_component in _device_discovery_components(
                device_discovery_payload
            ):
                component_id = device_component.component_id
                config = device_component.config
                component = config.pop(CONF_PLATFORM)
                if not config and device_discovery_diff is not None:
                    # Removing a component with only a platform is deprecated, the
                    # log can be removed in HA Core 2027.12, the skip must stay
                    _LOGGER.info(
                        "Ignoring %s '%s' with only the platform option in the MQTT "
                        "device discovery payload on topic %s%s; removing a component "
                        "this way is deprecated, omit it from the payload instead",
                        component,
                        _device_component_discovery_id(
                            object_id, node_id, component_id
                        ),
                        topic,
                        get_origin_log_string(
                            device_discovery_payload, include_url=False
                        ),
                    )
                    continue
                # The object_id in the device discovery topic is the unique identifier.
                # It is used as node_id for the components it contains.
                component_node_id = object_id
                # The component_id in the discovery playload is used as object_id
                # If we have an additional node_id in the discovery topic,
                # we extend the component_id with it.
                component_object_id = (
                    f"{node_id} {component_id}" if node_id else component_id
                )
                # We add wrapper to the discovery payload with the discovery data.
                # If the dict is empty after removing the platform, the payload is a
                # cleanup or migration of the device and we do not want to add
                # device or orig or shared availability attributes.
                if discovery_payload := MQTTDiscoveryPayload(config):
                    discovery_payload[CONF_DEVICE] = (
                        device_config
                        if device_component.child_device is None
                        # All components share the device config, so a component of
                        # a child device gets a new dict with its child device
                        else {
                            **device_config,
                            CONF_CHILD_DEVICE: device_component.child_device,
                        }
                    )
                    discovery_payload[CONF_ORIGIN] = origin_config
                    # Only assign shared config options
                    # when they are not set at entity level
                    _merge_common_device_options(
                        discovery_payload, device_discovery_payload
                    )
                discovery_payload.device_discovery = True
                discovery_payload.migrate_discovery = (
                    device_discovery_payload.migrate_discovery
                )
                discovered_components.append(
                    MqttComponentConfig(
                        component,
                        component_object_id,
                        component_node_id,
                        discovery_payload,
                    )
                )
            if device_discovery_diff is not None:
                _async_remove_omitted_device_components(
                    topic,
                    object_id,
                    device_discovery_payload,
                    device_discovery_diff,
                    discovered_components,
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
                _LOGGER.warning(
                    "Unable to parse JSON discovery payload on topic '%s': '%s'",
                    topic,
                    payload,
                )
                return
            if not _async_process_discovery_migration(discovery_payload):
                _replace_all_abbreviations(discovery_payload)
                if not _valid_origin_info(discovery_payload):
                    return
            discovered_components.append(
                MqttComponentConfig(component, object_id, node_id, discovery_payload)
            )

        discovery_pending_discovered = mqtt_data.discovery_pending_discovered
        for component_config in discovered_components:
            component = component_config.component
            node_id = component_config.node_id
            object_id = component_config.object_id
            discovery_payload = component_config.discovery_payload

            if TOPIC_BASE in discovery_payload:
                _replace_topic_base(discovery_payload)

            # If present, the node_id will be included in the discovery_id.
            discovery_id = f"{node_id} {object_id}" if node_id else object_id
            discovery_hash = (component, discovery_id)

            # Attach MQTT topic to the payload, used for debug prints
            discovery_payload.discovery_data = {
                ATTR_DISCOVERY_HASH: discovery_hash,
                ATTR_DISCOVERY_PAYLOAD: discovery_payload,
                ATTR_DISCOVERY_TOPIC: topic,
            }

            if discovery_hash in discovery_pending_discovered:
                pending = discovery_pending_discovered[discovery_hash]["pending"]
                pending.appendleft(discovery_payload)
                _LOGGER.debug(
                    "Component has already been discovered: %s %s, queuing update",
                    component,
                    discovery_id,
                )
                continue

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
                    discovery_pending_discovered[discovery_hash]["processing"] = payload
                    async_process_discovery_payload(component, discovery_id, payload)

            discovery_pending_discovered[discovery_hash] = {
                "unsub": async_dispatcher_connect(
                    hass,
                    MQTT_DISCOVERY_DONE.format(*discovery_hash),
                    discovery_done,
                ),
                "pending": deque(),
                "processing": payload,
            }

        if component not in mqtt_data.platforms_loaded and payload:
            # Load component first
            config_entry.async_create_task(
                hass, _async_component_setup(component, payload)
            )
        elif already_discovered:
            # Dispatch update
            message = (
                f"Component has already been discovered:"
                f" {component} {discovery_id}, sending update"
            )
            async_log_discovery_origin_info(message, payload)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_UPDATED.format(*discovery_hash), payload
            )
        elif payload:
            _async_add_component(payload)
        else:
            if payload.migrate_discovery:
                _async_untrack_disabled_entity_on_migration(
                    hass, discovery_hash, payload
                )
            elif (
                disabled_entity := mqtt_data.discovery_discovered_and_disabled.get(
                    discovery_hash
                )
            ) is not None:
                _async_cleanup_disabled_entity(
                    hass, discovery_hash, disabled_entity, payload
                )

            # Finish handling discovery message
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(*discovery_hash), None
            )

    discovery_qos: int = config_entry.options.get(CONF_DISCOVERY_QOS, 0)
    mqtt_data.discovery_unsubscribe = [
        async_subscribe_internal(
            hass,
            topic,
            async_discovery_message_received,
            discovery_qos,
            job_type=HassJobType.Callback,
        )
        # Subscribe first for platform discovery wildcard topics first,
        # and then subscribe device discovery wildcard topics.
        for topic in chain(
            (
                f"{discovery_topic}/{component}/+/config"
                for component in SUPPORTED_COMPONENTS
            ),
            (
                f"{discovery_topic}/{component}/+/+/config"
                for component in SUPPORTED_COMPONENTS
            ),
            (
                f"{discovery_topic}/device/+/config",
                f"{discovery_topic}/device/+/+/config",
            ),
        )
    ]

    mqtt_data.last_discovery = time.monotonic()
    mqtt_integrations = await async_get_mqtt(hass)
    integration_unsubscribe = mqtt_data.integration_unsubscribe

    async def _async_handle_config_entry_removed(entry: ConfigEntry) -> None:
        """Handle integration config entry changes."""
        for discovery_key in entry.discovery_keys[DOMAIN]:
            if (
                discovery_key.version != 1
                or not isinstance(discovery_key.key, str)
                or discovery_key.key not in integration_discovery_messages
            ):
                continue
            topic = discovery_key.key
            discovery_message = integration_discovery_messages[topic]
            del integration_discovery_messages[topic]
            _LOGGER.debug("Rediscover service on topic %s", topic)
            # Initiate re-discovery
            await async_integration_message_received(
                discovery_message.integration, discovery_message.msg
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
            msg.topic in integration_discovery_messages
            and integration_discovery_messages[msg.topic].msg.payload == msg.payload
        ):
            _LOGGER.debug(
                "Ignoring already processed discovery message for '%s' on topic %s: %s",
                integration,
                msg.topic,
                msg.payload,
            )
            return
        if TYPE_CHECKING:
            assert mqtt_data.data_config_flow_lock

        # Lock to prevent initiating many parallel config flows.
        # Note: The lock is not intended to prevent a race, only for performance
        async with mqtt_data.data_config_flow_lock:
            data = MqttServiceInfo(
                topic=msg.topic,
                payload=msg.payload,
                qos=msg.qos,
                retain=msg.retain,
                subscribed_topic=msg.subscribed_topic,
                timestamp=msg.timestamp,
            )
            discovery_key = discovery_flow.DiscoveryKey(
                domain=DOMAIN, key=msg.topic, version=1
            )
            discovery_flow.async_create_flow(
                hass,
                integration,
                {"source": SOURCE_MQTT},
                data,
                discovery_key=discovery_key,
            )
            if msg.payload:
                # Update the last discovered config message
                integration_discovery_messages[msg.topic] = (
                    MQTTIntegrationDiscoveryConfig(integration=integration, msg=msg)
                )
            elif msg.topic in integration_discovery_messages:
                # Cleanup cache if discovery payload is empty
                del integration_discovery_messages[msg.topic]

    integration_unsubscribe.update(
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
