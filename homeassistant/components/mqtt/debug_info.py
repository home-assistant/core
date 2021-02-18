"""Helper to handle a set of topics to subscribe to."""
from collections import deque
from functools import wraps
from typing import Any

from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_DISCOVERY_PAYLOAD, ATTR_DISCOVERY_TOPIC
from .models import MessageCallbackType

DATA_MQTT_DEBUG_INFO = "mqtt_debug_info"
STORED_MESSAGES = 10


def log_messages(hass: HomeAssistantType, entity_id: str) -> MessageCallbackType:
    """Wrap an MQTT message callback to support message logging."""

    def _log_message(msg):
        """Log message."""
        debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
        messages = debug_info["entities"][entity_id]["subscriptions"][
            msg.subscribed_topic
        ]["messages"]
        if msg not in messages:
            messages.append(msg)

    def _decorator(msg_callback: MessageCallbackType):
        @wraps(msg_callback)
        def wrapper(msg: Any) -> None:
            """Log message."""
            _log_message(msg)
            msg_callback(msg)

        setattr(wrapper, "__entity_id", entity_id)
        return wrapper

    return _decorator


def add_subscription(hass, message_callback, subscription):
    """Prepare debug data for subscription."""
    entity_id = getattr(message_callback, "__entity_id", None)
    if entity_id:
        debug_info = hass.data.setdefault(
            DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
        )
        entity_info = debug_info["entities"].setdefault(
            entity_id, {"subscriptions": {}, "discovery_data": {}}
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
    debug_info = hass.data.setdefault(
        DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
    )
    entity_info = debug_info["entities"].setdefault(
        entity_id, {"subscriptions": {}, "discovery_data": {}}
    )
    entity_info["discovery_data"] = discovery_data


def update_entity_discovery_data(hass, discovery_payload, entity_id):
    """Update discovery data."""
    entity_info = hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]
    entity_info["discovery_data"][ATTR_DISCOVERY_PAYLOAD] = discovery_payload


def remove_entity_data(hass, entity_id):
    """Remove discovery data."""
    hass.data[DATA_MQTT_DEBUG_INFO]["entities"].pop(entity_id)


def add_trigger_discovery_data(hass, discovery_hash, discovery_data, device_id):
    """Add discovery data."""
    debug_info = hass.data.setdefault(
        DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
    )
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


async def info_for_device(hass, device_id):
    """Get debug info for a device."""
    mqtt_info = {"entities": [], "triggers": []}
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entries = hass.helpers.entity_registry.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    mqtt_debug_info = hass.data.setdefault(
        DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
    )
    for entry in entries:
        if entry.entity_id not in mqtt_debug_info["entities"]:
            continue

        entity_info = mqtt_debug_info["entities"][entry.entity_id]
        subscriptions = [
            {
                "topic": topic,
                "messages": [
                    {
                        "payload": msg.payload,
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
        discovery_data = {
            "topic": entity_info["discovery_data"].get(ATTR_DISCOVERY_TOPIC, ""),
            "payload": entity_info["discovery_data"].get(ATTR_DISCOVERY_PAYLOAD, ""),
        }
        mqtt_info["entities"].append(
            {
                "entity_id": entry.entity_id,
                "subscriptions": subscriptions,
                "discovery_data": discovery_data,
            }
        )

    for trigger in mqtt_debug_info["triggers"].values():
        if trigger["device_id"] != device_id:
            continue

        discovery_data = {
            "topic": trigger["discovery_data"][ATTR_DISCOVERY_TOPIC],
            "payload": trigger["discovery_data"][ATTR_DISCOVERY_PAYLOAD],
        }
        mqtt_info["triggers"].append({"discovery_data": discovery_data})

    return mqtt_info
