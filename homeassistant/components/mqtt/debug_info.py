"""Helper to handle a set of topics to subscribe to."""
import asyncio
from functools import partial, wraps
import logging
from typing import Any

from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_DISCOVERY_PAYLOAD, ATTR_DISCOVERY_TOPIC
from .models import MessageCallbackType

_LOGGER = logging.getLogger(__name__)

DATA_MQTT_DEBUG_INFO = "mqtt_debug_info"
STORED_MESSAGES = 10


def log_messages(hass: HomeAssistantType, entity_id: str) -> MessageCallbackType:
    """Wrap an MQTT message callback to support message logging."""

    def _log_message(msg):
        """Log message."""
        debug_info = hass.data[DATA_MQTT_DEBUG_INFO]
        messages = debug_info["entities"][entity_id]["topics"][msg.topic]
        if len(messages) >= STORED_MESSAGES:
            messages.pop(0)
        messages.append(msg.payload)

    def _decorator(msg_callback: MessageCallbackType):
        # Check for partials to properly determine if coroutine function
        check_func = msg_callback
        while isinstance(check_func, partial):
            check_func = check_func.func

        wrapper_func = None
        if asyncio.iscoroutinefunction(check_func):

            @wraps(msg_callback)
            async def async_wrapper(msg: Any) -> None:
                """Log message."""
                _log_message(msg)
                await msg_callback(msg)

            wrapper_func = async_wrapper
        else:

            @wraps(msg_callback)
            def wrapper(msg: Any) -> None:
                """Log message."""
                _log_message(msg)
                msg_callback(msg)

            wrapper_func = wrapper
        setattr(wrapper_func, "__entity_id", entity_id)
        return wrapper_func

    return _decorator


def add_topic(hass, message_callback, topic):
    """Prepare debug data for topic."""
    entity_id = getattr(message_callback, "__entity_id", None)
    if entity_id:
        debug_info = hass.data.setdefault(
            DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
        )
        entity_info = debug_info["entities"].setdefault(
            entity_id, {"topics": {}, "discovery_data": {}}
        )
        entity_info["topics"][topic] = []


def remove_topic(hass, message_callback, topic):
    """Remove debug data for topic."""
    entity_id = getattr(message_callback, "__entity_id", None)
    if entity_id and entity_id in hass.data[DATA_MQTT_DEBUG_INFO]["entities"]:
        hass.data[DATA_MQTT_DEBUG_INFO]["entities"][entity_id]["topics"].pop(topic)


def add_entity_discovery_data(hass, discovery_data, entity_id):
    """Add discovery data."""
    debug_info = hass.data.setdefault(
        DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
    )
    entity_info = debug_info["entities"].setdefault(
        entity_id, {"topics": {}, "discovery_data": {}}
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
        entity_registry, device_id
    )
    mqtt_debug_info = hass.data.setdefault(
        DATA_MQTT_DEBUG_INFO, {"entities": {}, "triggers": {}}
    )
    for entry in entries:
        if entry.entity_id in mqtt_debug_info["entities"]:
            entity_info = mqtt_debug_info["entities"][entry.entity_id]
            topics = [
                {"topic": topic, "messages": messages}
                for topic, messages in entity_info["topics"].items()
            ]
            discovery_data = {
                "discovery_topic": entity_info["discovery_data"].get(
                    ATTR_DISCOVERY_TOPIC, ""
                ),
                "discovery_payload": entity_info["discovery_data"].get(
                    ATTR_DISCOVERY_PAYLOAD, ""
                ),
            }
            mqtt_info["entities"].append(
                {
                    "entity_id": entry.entity_id,
                    "topics": topics,
                    "discovery_data": discovery_data,
                }
            )

    for trigger in mqtt_debug_info["triggers"].values():
        if trigger["device_id"] == device_id:
            discovery_data = {
                "discovery_topic": trigger["discovery_data"][ATTR_DISCOVERY_TOPIC],
                "discovery_payload": trigger["discovery_data"][ATTR_DISCOVERY_PAYLOAD],
            }
            mqtt_info["triggers"].append({"discovery_data": discovery_data})

    return mqtt_info
