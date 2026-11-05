"""Explore the topics and payloads on the MQTT broker while someone is watching."""

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
MAX_PAYLOAD_SIZE = 16384
MESSAGES_PER_TOPIC = 5
MAX_TOPICS = 10000


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
        stats.messages += 1
        stats.bytes += size
        stats.interval_messages += 1
        stats.interval_bytes += size
        stats.last_received = received
        stats.retained = msg.retain
        stats.qos = msg.qos
        if (messages := self.new_messages.get(msg.topic)) is None:
            messages = self.new_messages[msg.topic] = deque(maxlen=MESSAGES_PER_TOPIC)
        messages.append(
            {
                "topic": msg.topic,
                "payload": _decode(payload[:MAX_PAYLOAD_SIZE]),
                "truncated": size > MAX_PAYLOAD_SIZE,
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
            },
            "topics": topics,
            "messages": messages,
        }


def _decode(payload: str | bytes | bytearray) -> str:
    """Return the payload as text, or its repr if it is not UTF-8."""
    if isinstance(payload, str):
        return payload
    try:
        return payload.decode(DEFAULT_ENCODING)
    except UnicodeDecodeError:
        return str(payload)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "mqtt/explorer/subscribe",
        probatio.Optional("topic", default="#"): valid_subscribe_topic,
        probatio.Optional("interval", default=DEFAULT_INTERVAL): probatio.All(
            probatio.Coerce(float), probatio.Range(min=1)
        ),
    }
)
@callback
def websocket_subscribe_explorer(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the topics and payloads below a topic filter until unsubscribed."""
    if DATA_MQTT not in hass.data:
        connection.send_error(msg["id"], "not_loaded", f"{DOMAIN} is not loaded")
        return

    interval: float = msg["interval"]
    client = hass.data[DATA_MQTT].client
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
    def unsubscribe() -> None:
        remove_timer()
        remove_subscription()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send_snapshot(None)
