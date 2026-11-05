"""Explore the topics and payloads on the MQTT broker while someone is watching."""

from codecs import getincrementaldecoder
from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .client import async_subscribe_internal
from .const import DEFAULT_ENCODING, DOMAIN
from .models import DATA_MQTT, ReceiveMessage
from .util import valid_subscribe_topic

DEFAULT_INTERVAL = 2
MAX_INTERVAL = 60
MAX_PAYLOAD_SIZE = 16384
MESSAGES_PER_TOPIC = 5
MAX_TOPICS = 10000
# Bounds the payload text buffered for and sent in one snapshot.
MAX_SNAPSHOT_PAYLOAD_SIZE = 1048576


@dataclass(slots=True)
class TopicStats:
    """Counters for one topic."""

    messages: int = 0
    bytes: int = 0
    interval_messages: int = 0
    interval_bytes: int = 0
    last_received: float = 0.0
    retained: bool = False
    qos: int = 0


@dataclass(slots=True, eq=False)
class TopicExplorer:
    """Topics and recent payloads seen since the explorer started."""

    started: float = field(default_factory=lambda: dt_util.utcnow().timestamp())
    topics: dict[str, TopicStats] = field(default_factory=dict)
    new_messages: dict[str, deque[dict[str, Any]]] = field(default_factory=dict)
    dropped_messages: int = 0
    dropped_payloads: int = 0
    buffered_payload_size: int = 0

    @callback
    def async_add_message(self, msg: ReceiveMessage) -> None:
        """Count a message and keep its payload until the next snapshot."""
        payload = msg.payload
        size = len(payload)
        if (stats := self.topics.get(msg.topic)) is None:
            if len(self.topics) >= MAX_TOPICS:
                self.dropped_messages += 1
                return
            stats = self.topics[msg.topic] = TopicStats()
        received = dt_util.utcnow().timestamp()
        truncated = size > MAX_PAYLOAD_SIZE
        stats.messages += 1
        stats.bytes += size
        stats.interval_messages += 1
        stats.interval_bytes += size
        stats.last_received = received
        stats.retained = msg.retain
        stats.qos = msg.qos
        if (messages := self.new_messages.get(msg.topic)) is None:
            messages = self.new_messages[msg.topic] = deque(maxlen=MESSAGES_PER_TOPIC)
        if self.buffered_payload_size >= MAX_SNAPSHOT_PAYLOAD_SIZE:
            self.dropped_payloads += 1
            return
        if len(messages) == MESSAGES_PER_TOPIC:
            self.buffered_payload_size -= len(messages[0]["payload"])
        text = _decode(payload, truncated)
        self.buffered_payload_size += len(text)
        messages.append(
            {
                "topic": msg.topic,
                "payload": text,
                "truncated": truncated,
                "size": size,
                "timestamp": received,
                "retain": msg.retain,
                "qos": msg.qos,
            }
        )

    @callback
    def async_snapshot(
        self, interval: float, subscriptions: dict[str, int]
    ) -> dict[str, Any]:
        """Return the topics that changed and their new messages."""
        topics: list[dict[str, Any]] = []
        interval_messages = interval_bytes = 0
        for topic in self.new_messages:
            stats = self.topics[topic]
            topics.append(
                {
                    "topic": topic,
                    "messages": stats.messages,
                    "bytes": stats.bytes,
                    "message_rate": stats.interval_messages / interval,
                    "byte_rate": stats.interval_bytes / interval,
                    "last_received": stats.last_received,
                    "retained": stats.retained,
                    "qos": stats.qos,
                    "subscriptions": subscriptions[topic],
                }
            )
            interval_messages += stats.interval_messages
            interval_bytes += stats.interval_bytes
            stats.interval_messages = stats.interval_bytes = 0
        messages = [
            message
            for topic_messages in self.new_messages.values()
            for message in topic_messages
        ]
        self.new_messages.clear()
        self.buffered_payload_size = 0
        return {
            "interval": interval,
            "now": dt_util.utcnow().timestamp(),
            "started": self.started,
            "total": {
                "topics": len(self.topics),
                "messages": sum(stats.messages for stats in self.topics.values()),
                "bytes": sum(stats.bytes for stats in self.topics.values()),
                "message_rate": interval_messages / interval,
                "byte_rate": interval_bytes / interval,
                "dropped_messages": self.dropped_messages,
                "dropped_payloads": self.dropped_payloads,
            },
            "topics": topics,
            "messages": messages,
        }


def _decode(payload: str | bytes | bytearray, truncated: bool) -> str:
    """Return the payload as text, or its repr if it is not UTF-8."""
    payload = payload[:MAX_PAYLOAD_SIZE]
    if isinstance(payload, str):
        return payload
    try:
        # Not final when truncated, so a code point cut in half is dropped.
        return getincrementaldecoder(DEFAULT_ENCODING)().decode(
            payload, final=not truncated
        )
    except UnicodeDecodeError:
        return str(payload)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "mqtt/explorer/subscribe",
        probatio.Optional("topic", default="#"): valid_subscribe_topic,
        probatio.Optional("interval", default=DEFAULT_INTERVAL): probatio.All(
            probatio.Coerce(float), probatio.Range(min=1, max=MAX_INTERVAL)
        ),
    }
)
@callback
def websocket_subscribe_explorer(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the topics and payloads below a topic filter until unsubscribed."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        connection.send_error(msg["id"], "not_loaded", f"{DOMAIN} is not loaded")
        return

    interval: float = msg["interval"]
    mqtt_data = hass.data[DATA_MQTT]
    client = mqtt_data.client
    explorer = TopicExplorer()
    remove_subscription = async_subscribe_internal(
        hass, msg["topic"], explorer.async_add_message, encoding=None
    )

    @callback
    def send_snapshot(_now: Any) -> None:
        # Leave out the explorer's own subscription.
        subscriptions = {
            topic: client.async_count_matching_subscriptions(topic) - 1
            for topic in explorer.new_messages
        }
        connection.send_message(
            websocket_api.event_message(
                msg["id"], explorer.async_snapshot(interval, subscriptions)
            )
        )

    remove_timer = async_track_time_interval(
        hass, send_snapshot, timedelta(seconds=interval)
    )

    @callback
    def stop() -> None:
        remove_timer()
        remove_subscription()

    @callback
    def unsubscribe() -> None:
        # Already stopped when MQTT was unloaded or reloaded.
        if stop in mqtt_data.reload_dispatchers:
            mqtt_data.reload_dispatchers.remove(stop)
            stop()

    # Stop before an unload stores the subscription to restore it on a new client.
    mqtt_data.reload_dispatchers.append(stop)
    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send_snapshot(None)
