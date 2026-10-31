"""Tests for the Meshtastic integration.

The library is mocked at the ``TCPInterface`` class boundary and its pubsub
publisher is replaced by :class:`FakePubSub`.  Tests inject packets by calling
the callbacks the integration registered, from the event-loop thread; no socket
is ever opened and no real thread is ever started.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

GATEWAY_NUM = 781534648
GATEWAY_ID = "!2e9545b8"
REMOTE_NUM = 2864434397
REMOTE_ID = "!aabbccdd"
SENSOR_NODE_NUM = 3735928559
SENSOR_NODE_ID = "!deadbeef"

TOPIC_CONNECTION_ESTABLISHED = "meshtastic.connection.established"
TOPIC_CONNECTION_LOST = "meshtastic.connection.lost"
TOPIC_RECEIVE = "meshtastic.receive"
TOPIC_NODE_UPDATED = "meshtastic.node.updated"
TOPIC_CLIENT_NOTIFICATION = "meshtastic.clientNotification"


class FakePubSub:
    """Stand-in for ``pubsub.pub`` that records and replays listeners.

    The real pypubsub publisher is a process-wide singleton with weak
    references; using it in tests leaks subscriptions between tests.  This
    records the subscriptions the client makes so a test can call them
    directly, and honours pypubsub's rule that a listener on a parent topic
    also receives sub-topics.
    """

    def __init__(self) -> None:
        """Initialise an empty publisher."""
        self.listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(
        self, listener: Callable[..., None], topic: str
    ) -> tuple[Callable[..., None], bool]:
        """Record a subscription."""
        self.listeners[topic].append(listener)
        return (listener, True)

    def unsubscribe(self, listener: Callable[..., None], topic: str) -> None:
        """Remove a subscription."""
        if listener in self.listeners[topic]:
            self.listeners[topic].remove(listener)

    def sendMessage(self, topic: str, **kwargs: Any) -> None:
        """Deliver a message to every listener of the topic or a parent."""
        for subscribed, listeners in list(self.listeners.items()):
            if topic == subscribed or topic.startswith(f"{subscribed}."):
                for listener in list(listeners):
                    listener(**kwargs)

    @property
    def subscribed_topics(self) -> set[str]:
        """Return the topics that currently have at least one listener."""
        return {topic for topic, listeners in self.listeners.items() if listeners}


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up a Meshtastic config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def inject_packet(
    hass: HomeAssistant,
    pubsub: FakePubSub,
    interface: MagicMock,
    packet: dict[str, Any],
    *,
    topic: str = TOPIC_RECEIVE,
) -> None:
    """Deliver one received packet as the library would."""
    pubsub.sendMessage(topic, packet=packet, interface=interface)
    await hass.async_block_till_done()


async def inject_node_info(
    hass: HomeAssistant,
    pubsub: FakePubSub,
    interface: MagicMock,
    node: dict[str, Any],
) -> None:
    """Deliver one node-DB push as the library would."""
    pubsub.sendMessage(TOPIC_NODE_UPDATED, node=node, interface=interface)
    await hass.async_block_till_done()


async def inject_notification(
    hass: HomeAssistant,
    pubsub: FakePubSub,
    interface: MagicMock,
    notification: Any,
) -> None:
    """Deliver one firmware client notification as the library would."""
    pubsub.sendMessage(
        TOPIC_CLIENT_NOTIFICATION, notification=notification, interface=interface
    )
    await hass.async_block_till_done()


async def inject_connection_lost(
    hass: HomeAssistant, pubsub: FakePubSub, interface: MagicMock
) -> None:
    """Report that the node closed the connection."""
    pubsub.sendMessage(TOPIC_CONNECTION_LOST, interface=interface)
    await hass.async_block_till_done()


async def inject_connection_established(
    hass: HomeAssistant, pubsub: FakePubSub, interface: MagicMock
) -> None:
    """Report that a handshake completed."""
    pubsub.sendMessage(TOPIC_CONNECTION_ESTABLISHED, interface=interface)
    await hass.async_block_till_done()
