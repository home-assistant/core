"""Helper to handle a set of topics to subscribe to."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from functools import wraps
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import ATTR_DISCOVERY_PAYLOAD, ATTR_DISCOVERY_TOPIC
from .models import MessageCallbackType, PublishPayloadType
from .util import get_mqtt_data

STORED_MESSAGES = 10


def log_messages(
    hass: HomeAssistant, entity_id: str
) -> Callable[[MessageCallbackType], MessageCallbackType]:
    """Wrap an MQTT message callback to support message logging."""

    debug_info_entities = get_mqtt_data(hass).debug_info_entities

    def _log_message(msg: Any) -> None:
        """Log message."""
        messages = debug_info_entities[entity_id]["subscriptions"][
            msg.subscribed_topic
        ]["messages"]
        if msg not in messages:
            messages.append(msg)

    def _decorator(msg_callback: MessageCallbackType) -> MessageCallbackType:
        @wraps(msg_callback)
        def wrapper(msg: Any) -> None:
            """Log message."""
            _log_message(msg)
            msg_callback(msg)

        setattr(wrapper, "__entity_id", entity_id)
        return wrapper

    return _decorator


@dataclass
class TimestampedPublishMessage:
    """MQTT Message."""

    topic: str
    payload: PublishPayloadType
    qos: int
    retain: bool
    timestamp: dt.datetime


def log_message(
    hass: HomeAssistant,
    entity_id: str,
    topic: str,
    payload: PublishPayloadType,
    qos: int,
    retain: bool,
) -> None:
    """Log an outgoing MQTT message."""
    entity_info = get_mqtt_data(hass).debug_info_entities.setdefault(
        entity_id, {"subscriptions": {}, "discovery_data": {}, "transmitted": {}}
    )
    if topic not in entity_info["transmitted"]:
        entity_info["transmitted"][topic] = {
            "messages": deque([], STORED_MESSAGES),
        }
    msg = TimestampedPublishMessage(
        topic, payload, qos, retain, timestamp=dt_util.utcnow()
    )
    entity_info["transmitted"][topic]["messages"].append(msg)


def add_subscription(
    hass: HomeAssistant,
    message_callback: MessageCallbackType,
    subscription: str,
) -> None:
    """Prepare debug data for subscription."""
    if entity_id := getattr(message_callback, "__entity_id", None):
        entity_info = get_mqtt_data(hass).debug_info_entities.setdefault(
            entity_id, {"subscriptions": {}, "discovery_data": {}, "transmitted": {}}
        )
        if subscription not in entity_info["subscriptions"]:
            entity_info["subscriptions"][subscription] = {
                "count": 0,
                "messages": deque([], STORED_MESSAGES),
            }
        entity_info["subscriptions"][subscription]["count"] += 1


def remove_subscription(
    hass: HomeAssistant,
    message_callback: MessageCallbackType,
    subscription: str,
) -> None:
    """Remove debug data for subscription if it exists."""
    if (entity_id := getattr(message_callback, "__entity_id", None)) and entity_id in (
        debug_info_entities := get_mqtt_data(hass).debug_info_entities
    ):
        debug_info_entities[entity_id]["subscriptions"][subscription]["count"] -= 1
        if not debug_info_entities[entity_id]["subscriptions"][subscription]["count"]:
            debug_info_entities[entity_id]["subscriptions"].pop(subscription)


def add_entity_discovery_data(
    hass: HomeAssistant, discovery_data: DiscoveryInfoType, entity_id: str
) -> None:
    """Add discovery data."""
    entity_info = get_mqtt_data(hass).debug_info_entities.setdefault(
        entity_id, {"subscriptions": {}, "discovery_data": {}, "transmitted": {}}
    )
    entity_info["discovery_data"] = discovery_data


def update_entity_discovery_data(
    hass: HomeAssistant, discovery_payload: DiscoveryInfoType, entity_id: str
) -> None:
    """Update discovery data."""
    discovery_data = get_mqtt_data(hass).debug_info_entities[entity_id][
        "discovery_data"
    ]
    if TYPE_CHECKING:
        assert discovery_data is not None
    discovery_data[ATTR_DISCOVERY_PAYLOAD] = discovery_payload


def remove_entity_data(hass: HomeAssistant, entity_id: str) -> None:
    """Remove discovery data."""
    if entity_id in (debug_info_entities := get_mqtt_data(hass).debug_info_entities):
        debug_info_entities.pop(entity_id)


def add_trigger_discovery_data(
    hass: HomeAssistant,
    discovery_hash: tuple[str, str],
    discovery_data: DiscoveryInfoType,
    device_id: str,
) -> None:
    """Add discovery data."""
    get_mqtt_data(hass).debug_info_triggers[discovery_hash] = {
        "device_id": device_id,
        "discovery_data": discovery_data,
    }


def update_trigger_discovery_data(
    hass: HomeAssistant,
    discovery_hash: tuple[str, str],
    discovery_payload: DiscoveryInfoType,
) -> None:
    """Update discovery data."""
    get_mqtt_data(hass).debug_info_triggers[discovery_hash]["discovery_data"][
        ATTR_DISCOVERY_PAYLOAD
    ] = discovery_payload


def remove_trigger_discovery_data(
    hass: HomeAssistant, discovery_hash: tuple[str, str]
) -> None:
    """Remove discovery data."""
    get_mqtt_data(hass).debug_info_triggers.pop(discovery_hash)


def _info_for_entity(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    entity_info = get_mqtt_data(hass).debug_info_entities[entity_id]
    subscriptions = [
        {
            "topic": topic,
            "messages": [
                {
                    "payload": str(msg.payload),
                    "qos": msg.qos,
                    "retain": msg.retain,
                    "time": msg.timestamp,
                    "topic": msg.topic,
                }
                for msg in subscription["messages"]
            ],
        }
        for topic, subscription in entity_info["subscriptions"].items()
    ]
    transmitted = [
        {
            "topic": topic,
            "messages": [
                {
                    "payload": str(msg.payload),
                    "qos": msg.qos,
                    "retain": msg.retain,
                    "time": msg.timestamp,
                    "topic": msg.topic,
                }
                for msg in subscription["messages"]
            ],
        }
        for topic, subscription in entity_info["transmitted"].items()
    ]
    discovery_data = {
        "topic": entity_info["discovery_data"].get(ATTR_DISCOVERY_TOPIC, ""),
        "payload": entity_info["discovery_data"].get(ATTR_DISCOVERY_PAYLOAD, ""),
    }

    return {
        "entity_id": entity_id,
        "subscriptions": subscriptions,
        "discovery_data": discovery_data,
        "transmitted": transmitted,
    }


def _info_for_trigger(
    hass: HomeAssistant, trigger_key: tuple[str, str]
) -> dict[str, Any]:
    trigger = get_mqtt_data(hass).debug_info_triggers[trigger_key]
    discovery_data = None
    if trigger["discovery_data"] is not None:
        discovery_data = {
            "topic": trigger["discovery_data"][ATTR_DISCOVERY_TOPIC],
            "payload": trigger["discovery_data"][ATTR_DISCOVERY_PAYLOAD],
        }
    return {"discovery_data": discovery_data, "trigger_key": trigger_key}


def info_for_config_entry(hass: HomeAssistant) -> dict[str, list[Any]]:
    """Get debug info for all entities and triggers."""

    mqtt_data = get_mqtt_data(hass)
    mqtt_info: dict[str, list[Any]] = {"entities": [], "triggers": []}

    for entity_id in mqtt_data.debug_info_entities:
        mqtt_info["entities"].append(_info_for_entity(hass, entity_id))

    for trigger_key in mqtt_data.debug_info_triggers:
        mqtt_info["triggers"].append(_info_for_trigger(hass, trigger_key))

    return mqtt_info


def info_for_device(hass: HomeAssistant, device_id: str) -> dict[str, list[Any]]:
    """Get debug info for a device."""

    mqtt_data = get_mqtt_data(hass)

    mqtt_info: dict[str, list[Any]] = {"entities": [], "triggers": []}
    entity_registry = er.async_get(hass)

    entries = er.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    for entry in entries:
        if entry.entity_id not in mqtt_data.debug_info_entities:
            continue

        mqtt_info["entities"].append(_info_for_entity(hass, entry.entity_id))

    for trigger_key, trigger in mqtt_data.debug_info_triggers.items():
        if trigger["device_id"] != device_id:
            continue

        mqtt_info["triggers"].append(_info_for_trigger(hass, trigger_key))

    return mqtt_info
