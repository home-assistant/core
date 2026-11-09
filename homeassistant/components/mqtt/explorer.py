"""Websocket API to explore how MQTT items are set up."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.typing import DiscoveryInfoType

from . import debug_info
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_BROKER,
    CONF_CHILD_DEVICE,
    CONF_COMPONENTS,
    CONF_DISCOVERY_PREFIX,
    CONF_ORIGIN,
    CONF_QOS,
    CONF_TOPIC,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_QOS,
    DOMAIN,
)
from .models import DATA_MQTT

SOURCE_DISCOVERY = "discovery"
SOURCE_SUBENTRY = "subentry"
SOURCE_YAML = "yaml"

ARTIFACT_DEVICE_TRIGGER = "device_trigger"
ARTIFACT_TAG = "tag"


def _origin_as_dict(origin: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": origin["name"],
        "sw_version": origin.get("sw_version"),
        "support_url": origin.get("support_url"),
    }


class _Sources:
    """Collect the sources that MQTT items were set up from."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self.sources: dict[str, dict[str, Any]] = {}

    @callback
    def _add(
        self,
        source_id: str,
        source_type: str,
        title: str | None = None,
        origin: dict[str, Any] | None = None,
    ) -> str:
        # Called for every item, so only build the source the first time
        if source_id not in self.sources:
            self.sources[source_id] = {
                "id": source_id,
                "type": source_type,
                "title": title,
                "sw_version": origin.get("sw_version") if origin else None,
            }
        return source_id

    @callback
    def discovery(self, discovery_payload: DiscoveryInfoType) -> str:
        """Return the source ID for a discovery payload."""
        if (origin := discovery_payload.get(CONF_ORIGIN)) is None:
            return self._add(SOURCE_DISCOVERY, SOURCE_DISCOVERY)
        name: str = origin["name"]
        return self._add(f"origin:{name}", SOURCE_DISCOVERY, name, origin)

    @callback
    def subentry(self, subentry_id: str) -> str:
        """Return the source ID for a subentry."""
        source_id = f"{SOURCE_SUBENTRY}:{subentry_id}"
        if source_id in self.sources:
            return source_id
        return self._add(
            source_id, SOURCE_SUBENTRY, self._entry.subentries[subentry_id].title
        )

    @callback
    def yaml(self) -> str:
        """Return the source ID for YAML."""
        return self._add(SOURCE_YAML, SOURCE_YAML)


@callback
def _entity_discovery_data(
    hass: HomeAssistant, entity_id: str
) -> DiscoveryInfoType | None:
    if (
        entity_info := hass.data[DATA_MQTT].debug_info_entities.get(entity_id)
    ) is None or not entity_info["discovery_data"]:
        return None
    return entity_info["discovery_data"]


@callback
def _entity_source(
    hass: HomeAssistant,
    sources: _Sources,
    entity_id: str,
    registry_entry: er.RegistryEntry | None,
) -> str:
    if (discovery_data := _entity_discovery_data(hass, entity_id)) is not None:
        return sources.discovery(discovery_data[ATTR_DISCOVERY_PAYLOAD])
    if registry_entry is not None and registry_entry.config_subentry_id is not None:
        return sources.subentry(registry_entry.config_subentry_id)
    return sources.yaml()


@callback
def _artifacts(hass: HomeAssistant) -> list[tuple[str, str, str, DiscoveryInfoType]]:
    """Return artifact ID, type, device ID and discovery data of all artifacts."""
    mqtt_data = hass.data[DATA_MQTT]
    artifacts: list[tuple[str, str, str, DiscoveryInfoType]] = [
        (
            f"{ARTIFACT_DEVICE_TRIGGER}:{discovery_id}",
            ARTIFACT_DEVICE_TRIGGER,
            trigger["device_id"],
            trigger["discovery_data"],
        )
        for (_, discovery_id), trigger in mqtt_data.debug_info_triggers.items()
        if trigger["discovery_data"] is not None
    ]
    artifacts.extend(
        (
            f"{ARTIFACT_TAG}:{discovery_id}",
            ARTIFACT_TAG,
            device_id,
            tag_scanner.discovery_data,
        )
        for device_id, tag_scanners in mqtt_data.tags.items()
        for discovery_id, tag_scanner in tag_scanners.items()
    )
    return artifacts


def _artifact_topics(
    discovery_data: DiscoveryInfoType, include_messages: bool
) -> list[dict[str, Any]]:
    """Return the topic a device trigger or tag subscribes to.

    The debug info keeps no messages for them, so there are no stored messages.
    """
    payload = discovery_data[ATTR_DISCOVERY_PAYLOAD]
    if CONF_TOPIC not in payload:
        return []
    topic: dict[str, Any] = {
        "topic": payload[CONF_TOPIC],
        "direction": "subscribe",
        "qos": payload.get(CONF_QOS, DEFAULT_QOS),
    }
    if include_messages:
        topic["messages"] = []
    return [topic]


@callback
def _entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, er.RegistryEntry | None]:
    """Return the IDs of the enabled MQTT entities, with their registry entry."""
    entity_ids: dict[str, er.RegistryEntry | None] = {
        registry_entry.entity_id: registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if not registry_entry.disabled
    }
    # Entities without a unique ID are not in the entity registry
    for entity_id in hass.data[DATA_MQTT].debug_info_entities:
        entity_ids.setdefault(entity_id, None)
    return entity_ids


def _node_id(discovery_data: DiscoveryInfoType, discovery_prefix: str) -> str | None:
    """Return the node ID of the discovery topic, if it has one."""
    # <discovery_prefix>/<component>/[<node_id>/]<object_id>/config
    parts = (
        discovery_data[ATTR_DISCOVERY_TOPIC]
        .removeprefix(f"{discovery_prefix}/")
        .split("/")
    )
    return parts[1] if len(parts) == 4 else None


@callback
def _async_structure(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    conf = entry.data | entry.options
    discovery_prefix: str = conf.get(CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX)
    sources = _Sources(entry)
    device_sources: dict[str, set[str]] = {}

    # Devices that only have entities that were not set up
    devices_not_set_up: set[str] = set()

    entities: list[dict[str, Any]] = []
    for entity_id, registry_entry in _entity_ids(hass, entry).items():
        device_id = registry_entry.device_id if registry_entry else None
        state = hass.states.get(entity_id)
        source: str | None
        if (
            registry_entry is not None
            and registry_entry.config_subentry_id is None
            and (state is None or state.attributes.get(EntityStateAttribute.RESTORED))
        ):
            # Not set up, so a discovered entity whose discovery was not
            # received; its origin is unknown, so it is placed under its device
            if device_id is None:
                source = sources.discovery({})
            else:
                source = None
                devices_not_set_up.add(device_id)
        else:
            source = _entity_source(hass, sources, entity_id, registry_entry)
            if device_id is not None:
                device_sources.setdefault(device_id, set()).add(source)
        name: str | None = None
        if state is not None:
            name = state.name
        elif registry_entry is not None:
            name = registry_entry.original_name
        discovery_data = _entity_discovery_data(hass, entity_id)
        entities.append(
            {
                "entity_id": entity_id,
                "name": name,
                "available": state is not None and state.state != STATE_UNAVAILABLE,
                "source": source,
                "device_id": device_id,
                "node_id": _node_id(discovery_data, discovery_prefix)
                if discovery_data
                else None,
                "topics": debug_info.topics_for_entity(
                    hass, entity_id, include_messages=False
                ),
            }
        )

    artifacts: list[dict[str, Any]] = []
    for artifact_id, artifact_type, device_id, discovery_data in _artifacts(hass):
        source = sources.discovery(discovery_data[ATTR_DISCOVERY_PAYLOAD])
        device_sources.setdefault(device_id, set()).add(source)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "type": artifact_type,
                "source": source,
                "device_id": device_id,
                "node_id": _node_id(discovery_data, discovery_prefix),
                "topics": _artifact_topics(discovery_data, include_messages=False),
            }
        )

    device_registry = dr.async_get(hass)
    device_entries: list[AnyDeviceEntry] = [
        *dr.async_entries_for_config_entry(device_registry, entry.entry_id),
        *dr.async_child_entries_for_config_entry(device_registry, entry.entry_id),
    ]
    parent_device_ids: dict[str, str | None] = {
        device.id: device.parent_device_id
        if isinstance(device, dr.ChildDeviceEntry)
        else device.via_device_id
        for device in device_entries
    }
    for device in device_entries:
        if device.config_subentry_id is not None:
            device_sources.setdefault(device.id, set()).add(
                sources.subentry(device.config_subentry_id)
            )
        elif device.id in devices_not_set_up and device.id not in device_sources:
            device_sources[device.id] = {sources.discovery({})}
    child_device_ids: dict[str, list[str]] = {}
    for device_id, parent_device_id in parent_device_ids.items():
        if parent_device_id is not None:
            child_device_ids.setdefault(parent_device_id, []).append(device_id)

    def _device_source_ids(device_id: str, seen: set[str]) -> set[str]:
        """Return the sources of a device's items, else those of its child devices."""
        if own_source_ids := device_sources.get(device_id):
            return own_source_ids
        source_ids: set[str] = set()
        for child_device_id in child_device_ids.get(device_id, []):
            if child_device_id not in seen:
                source_ids |= _device_source_ids(
                    child_device_id, seen | {child_device_id}
                )
        return source_ids

    devices = [
        {
            "device_id": device.id,
            "name": device.name_by_user or device.name,
            "sources": sorted(device_source_ids),
            "via_device_id": parent_device_ids[device.id],
            "child_device": isinstance(device, dr.ChildDeviceEntry),
        }
        for device in device_entries
        # Devices stay in the registry after their items are gone; leave those out
        if (device_source_ids := _device_source_ids(device.id, {device.id}))
    ]

    return {
        "broker": {
            "connected": hass.data[DATA_MQTT].client.connected,
            "host": conf[CONF_BROKER],
            "port": conf.get(CONF_PORT, DEFAULT_PORT),
        },
        "sources": sorted(sources.sources.values(), key=lambda item: item["id"]),
        "devices": sorted(devices, key=lambda item: item["device_id"]),
        "entities": sorted(entities, key=lambda item: item["entity_id"]),
        "artifacts": sorted(artifacts, key=lambda item: item["artifact_id"]),
    }


def _is_device_discovery(discovery_data: DiscoveryInfoType) -> bool:
    """Return if an item came from a device based discovery payload."""
    return getattr(discovery_data[ATTR_DISCOVERY_PAYLOAD], "device_discovery", False)


def _discovery_config(source: str, discovery_data: DiscoveryInfoType) -> dict[str, Any]:
    payload: dict[str, Any] = dict(discovery_data[ATTR_DISCOVERY_PAYLOAD])
    origin = payload.get(CONF_ORIGIN)
    return {
        "source": source,
        "type": SOURCE_DISCOVERY,
        "discovery_topic": discovery_data[ATTR_DISCOVERY_TOPIC],
        "origin": _origin_as_dict(origin) if origin else None,
        "payload": payload,
        "device_payload": payload.get(CONF_DEVICE),
        "device_discovery": _is_device_discovery(discovery_data),
    }


def _add_device_discovery_component(
    configs: dict[str, dict[str, Any]], source: str, discovery_data: DiscoveryInfoType
) -> None:
    """Add a component to the config of the device discovery it came from.

    The device discovery payload itself is not kept, so it is built again from
    its components, which each hold the device and origin.
    """
    topic: str = discovery_data[ATTR_DISCOVERY_TOPIC]
    payload: dict[str, Any] = dict(discovery_data[ATTR_DISCOVERY_PAYLOAD])
    device_payload: dict[str, Any] = dict(payload.pop(CONF_DEVICE, None) or {})
    device_payload.pop(CONF_CHILD_DEVICE, None)
    origin = payload.pop(CONF_ORIGIN, None)
    config = configs.setdefault(
        topic,
        {
            "source": source,
            "type": SOURCE_DISCOVERY,
            "discovery_topic": topic,
            "origin": _origin_as_dict(origin) if origin else None,
            "payload": {CONF_DEVICE: device_payload}
            | ({CONF_ORIGIN: origin} if origin else {})
            | {CONF_COMPONENTS: {}},
            "device_payload": device_payload,
            "device_discovery": True,
        },
    )
    platform, discovery_id = discovery_data[ATTR_DISCOVERY_HASH]
    # The discovery ID ends with the component ID of the device discovery payload
    component_id = discovery_id.rsplit(" ", 1)[-1]
    config["payload"][CONF_COMPONENTS][component_id] = {
        CONF_PLATFORM: platform
    } | payload


def _yaml_config(
    hass: HomeAssistant, source: str, entity_id: str, unique_id: str
) -> dict[str, Any] | None:
    domain = entity_id.split(".", 1)[0]
    for config_item in hass.data[DATA_MQTT].config:
        for config in config_item.get(domain, []):
            # The YAML is not validated yet, so a unique ID can be a number
            if CONF_UNIQUE_ID in config and str(config[CONF_UNIQUE_ID]) == unique_id:
                return {
                    "source": source,
                    "type": SOURCE_YAML,
                    "discovery_topic": None,
                    "origin": None,
                    "payload": dict(config),
                    "device_payload": config.get(CONF_DEVICE),
                    "device_discovery": False,
                }
    return None


def _subentry_config(
    entry: ConfigEntry, source: str, subentry_id: str, unique_id: str | None
) -> dict[str, Any]:
    subentry_data = entry.subentries[subentry_id].data
    payload: dict[str, Any] = {}
    if unique_id is not None:
        component_id = unique_id.removeprefix(f"{subentry_id}_")
        payload = dict(subentry_data["components"].get(component_id, {}))
    return {
        "source": source,
        "type": SOURCE_SUBENTRY,
        "discovery_topic": None,
        "origin": None,
        "payload": payload,
        "device_payload": dict(subentry_data["device"]),
        "device_discovery": False,
    }


@callback
def _async_entity_config(
    hass: HomeAssistant,
    entry: ConfigEntry,
    sources: _Sources,
    entity_id: str,
    registry_entry: er.RegistryEntry | None,
) -> dict[str, Any] | None:
    source = _entity_source(hass, sources, entity_id, registry_entry)
    if (discovery_data := _entity_discovery_data(hass, entity_id)) is not None:
        return _discovery_config(source, discovery_data)
    if registry_entry is None:
        # YAML entities without a unique ID cannot be matched to their config
        return None
    if registry_entry.config_subentry_id is not None:
        return _subentry_config(
            entry, source, registry_entry.config_subentry_id, registry_entry.unique_id
        )
    return _yaml_config(hass, source, entity_id, registry_entry.unique_id)


def _device_part(config: dict[str, Any]) -> dict[str, Any]:
    """Return the config of a device, taken from the config of one of its items."""
    return config | {"payload": config["device_payload"] or {}}


def _config_result(config: dict[str, Any]) -> dict[str, Any]:
    """Return a config without its device part, which only builds device configs."""
    return {key: value for key, value in config.items() if key != "device_payload"}


@callback
def _async_details(
    hass: HomeAssistant, entry: ConfigEntry, msg: dict[str, Any]
) -> dict[str, Any] | None:
    sources = _Sources(entry)
    entity_ids = _entity_ids(hass, entry)

    if (entity_id := msg.get("entity_id")) is not None:
        if entity_id not in entity_ids:
            return None
        config = _async_entity_config(
            hass, entry, sources, entity_id, entity_ids[entity_id]
        )
        return {
            "configs": [_config_result(config)] if config else [],
            "topics": debug_info.topics_for_entity(
                hass, entity_id, include_messages=True
            ),
        }

    artifacts = _artifacts(hass)
    if (artifact_id := msg.get("artifact_id")) is not None:
        for item_id, _, _, discovery_data in artifacts:
            if item_id == artifact_id:
                source = sources.discovery(discovery_data[ATTR_DISCOVERY_PAYLOAD])
                return {
                    "configs": [
                        _config_result(_discovery_config(source, discovery_data))
                    ],
                    "topics": _artifact_topics(discovery_data, include_messages=True),
                }
        return None

    device_id: str = msg["device_id"]
    device = dr.async_get(hass).async_get(device_id)
    if device is None or device.config_entry_id != entry.entry_id:
        return None
    # The device part per source, and the device discovery configs per topic
    configs: dict[str, dict[str, Any]] = {}
    device_discovery_configs: dict[str, dict[str, Any]] = {}
    for entity_id, registry_entry in entity_ids.items():
        if registry_entry is None or registry_entry.device_id != device_id:
            continue
        if (
            entity_discovery_data := _entity_discovery_data(hass, entity_id)
        ) is not None and _is_device_discovery(entity_discovery_data):
            _add_device_discovery_component(
                device_discovery_configs,
                sources.discovery(entity_discovery_data[ATTR_DISCOVERY_PAYLOAD]),
                entity_discovery_data,
            )
        elif (
            config := _async_entity_config(
                hass, entry, sources, entity_id, registry_entry
            )
        ) is not None:
            configs.setdefault(config["source"], _device_part(config))
    for _, _, artifact_device_id, discovery_data in artifacts:
        if artifact_device_id != device_id:
            continue
        source = sources.discovery(discovery_data[ATTR_DISCOVERY_PAYLOAD])
        if _is_device_discovery(discovery_data):
            _add_device_discovery_component(
                device_discovery_configs, source, discovery_data
            )
        else:
            configs.setdefault(
                source, _device_part(_discovery_config(source, discovery_data))
            )
    if (subentry_id := device.config_subentry_id) is not None:
        source = sources.subentry(subentry_id)
        configs.setdefault(
            source, _device_part(_subentry_config(entry, source, subentry_id, None))
        )
    return {
        "configs": [
            _config_result(config)
            for config in [configs[source] for source in sorted(configs)]
            + [
                device_discovery_configs[topic]
                for topic in sorted(device_discovery_configs)
            ]
        ],
        "topics": [],
    }


@callback
def _loaded_entry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int
) -> ConfigEntry | None:
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        connection.send_error(msg_id, "not_loaded", f"{DOMAIN} is not loaded")
        return None
    return entries[0]


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "mqtt/explorer/structure"})
@callback
def websocket_explorer_structure(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the sources, devices, entities, topics and artifacts of MQTT."""
    if (entry := _loaded_entry(hass, connection, msg["id"])) is None:
        return
    connection.send_result(msg["id"], _async_structure(hass, entry))


@websocket_api.require_admin
@websocket_api.websocket_command(
    probatio.All(
        probatio.Schema(
            {
                probatio.Required("type"): "mqtt/explorer/details",
                probatio.Exclusive("device_id", "item"): str,
                probatio.Exclusive("entity_id", "item"): str,
                probatio.Exclusive("artifact_id", "item"): str,
            }
        ),
        probatio.AtLeastOne("device_id", "entity_id", "artifact_id"),
    )
)
@callback
def websocket_explorer_details(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the config and stored messages of an MQTT device, entity or artifact."""
    if (entry := _loaded_entry(hass, connection, msg["id"])) is None:
        return
    if (details := _async_details(hass, entry, msg)) is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "MQTT item not found"
        )
        return
    connection.send_result(msg["id"], details)
