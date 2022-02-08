"""Helper to handle a set of topics to subscribe to."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
import datetime as dt
from functools import wraps
from typing import Any

import attr

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import ATTR_DISCOVERY_PAYLOAD, ATTR_DISCOVERY_TOPIC
from .models import MessageCallbackType, PublishPayloadType

DATA_MQTT_DEBUG_INFO = "mqtt_debug_info"
STORED_MESSAGES = 10


def initialize(hass: HomeAssistant):
    """Initialize MQTT debug info."""
    hass.data[DATA_MQTT_DEBUG_INFO] = {"entities": {}, "triggers": {}}


def log_messages(
    hass: HomeAssistant, entity_id: str
) -> Callable[[MessageCallbackType], MessageCallbackType]:
    """Wrap an MQTT message callback to support message logging."""

    def _log_message(msg):
        """Log message."""
        debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
        messages = debug_info["entities"][entity_id]["subscriptions"][
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


@attr.s(slots=True, frozen=True)
class TimestampedPublishMessage:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: PublishPayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()
    timestamp: dt.datetime = attr.ib(default=None)


def log_message(
    hass: HomeAssistant,
    entity_id: str,
    topic: str,
    payload: PublishPayloadType,
    qos: int,
    retain: bool,
) -> None:
    """Log an outgoing MQTT message."""
    debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
    entity_info = debug_info["entities"].setdefault(
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


def add_subscription(hass, message_callback, subscription):
    """Prepare debug data for subscription."""
    if entity_id := getattr(message_callback, "__entity_id", None):
        debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
        entity_info = debug_info["entities"].setdefault(
            entity_id, {"subscriptions": {}, "discovery_data": {}, "transmitted": {}}
        )
        if subscription not in entity_info["subscriptions"]:
            entity_info["subscriptions"][subscription] = {
                "count": 0,
                "messages": deque([], STORED_MESSAGES),
            }
        entity_info["subscriptions"][subscription]["count"] += 1


def remove_subscription(hass, message_callback, subscription):
    """Remove debug data for subscription if it exists."""
    entity_id = getattr(message_callback, "__entity_id", None)
    if entity_id and entity_id in hass.data[DATA_MQTT_DEBUG_INFO]["entities"]:
        hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]["subscriptions"][
            subscription
        ]["count"] -= 1
        if not hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]["subscriptions"][
            subscription
        ]["count"]:
            hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]["subscriptions"].pop(
                subscription
            )


def add_entity_discovery_data(hass, discovery_data, entity_id):
    """Add discovery data."""
    debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
    entity_info = debug_info["entities"].setdefault(
        entity_id, {"subscriptions": {}, "discovery_data": {}, "transmitted": {}}
    )
    entity_info["discovery_data"] = discovery_data


def update_entity_discovery_data(hass, discovery_payload, entity_id):
    """Update discovery data."""
    entity_info = hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]
    entity_info["discovery_data"][ATTR_DISCOVERY_PAYLOAD] = discovery_payload


def remove_entity_data(hass, entity_id):
    """Remove discovery data."""
    if entity_id in hass.data[DATA_MQTT_DEBUG_INFO]["entities"]:
        hass.data[DATA_MQTT_DEBUG_INFO]["entities"].pop(entity_id)


def add_trigger_discovery_data(hass, discovery_hash, discovery_data, device_id):
    """Add discovery data."""
    debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
    debug_info["triggers"][discovery_hash] = {
        "device_id": device_id,
        "discovery_data": discovery_data,
    }


def update_trigger_discovery_data(hass, discovery_hash, discovery_payload):
    """Update discovery data."""
    trigger_info = hass.data[DATA_MQTT_DEBUG_INFO]["triggers"][discovery_hash]
    trigger_info["discovery_data"][ATTR_DISCOVERY_PAYLOAD] = discovery_payload


def remove_trigger_discovery_data(hass, discovery_hash):
    """Remove discovery data."""
    hass.data[DATA_MQTT_DEBUG_INFO]["triggers"][discovery_hash]["discovery_data"] = None


def info_for_device(hass, device_id):
    """Get debug info for a device."""
    mqtt_info = {"entities": [], "triggers": []}
    entity_registry = er.async_get(hass)

    entries = hass.helpers.entity_registry.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    mqtt_debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
    for entry in entries:
        if entry.entity_id not in mqtt_debug_info["entities"]:
            continue

        entity_info = mqtt_debug_info["entities"][entry.entity_id]
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
                    for msg in list(subscription["messages"])
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
                    for msg in list(subscription["messages"])
                ],
            }
            for topic, subscription in entity_info["transmitted"].items()
        ]
        discovery_data = {
            "topic": entity_info["discovery_data"].get(ATTR_DISCOVERY_TOPIC, ""),
            "payload": entity_info["discovery_data"].get(ATTR_DISCOVERY_PAYLOAD, ""),
        }
        mqtt_info["entities"].append(
            {
                "entity_id": entry.entity_id,
                "subscriptions": subscriptions,
                "discovery_data": discovery_data,
                "transmitted": transmitted,
            }
        )

    for trigger in mqtt_debug_info["triggers"].values():
        if trigger["device_id"] != device_id or trigger["discovery_data"] is None:
            continue

        discovery_data = {
            "topic": trigger["discovery_data"][ATTR_DISCOVERY_TOPIC],
            "payload": trigger["discovery_data"][ATTR_DISCOVERY_PAYLOAD],
        }
        mqtt_info["triggers"].append({"discovery_data": discovery_data})

    return mqtt_info
