"""Support for sending Meshtastic text messages."""

from typing import override

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .client import raise_for_result
from .const import BROADCAST_NUM
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import MeshtasticChannel, MeshtasticNode

PARALLEL_UPDATES = 1


def _body(message: str, title: str | None) -> str:
    """Return the text to put on the air for one notification.

    A Meshtastic packet has no title field, so a title becomes a prefix.  The
    client rejects the result if it does not fit in a packet.
    """
    return f"{title}: {message}" if title else message


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic notify entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    known_channels: set[int] = set()
    known_nodes: set[str] = set()

    @callback
    def _check_targets() -> None:
        data = coordinator.data
        channels = [
            channel
            for channel in data.gateway.channels
            if channel.index not in known_channels
        ]
        nodes = [
            node
            for node_id, node in data.nodes.items()
            if node_id not in known_nodes
            and not node.presumptive
            # Sending a direct message to the gateway itself is a no-op; its
            # own device carries the channel entities instead.
            and node.num != data.gateway.node_num
        ]
        if not channels and not nodes:
            return
        known_channels.update(channel.index for channel in channels)
        known_nodes.update(node.node_id for node in nodes)
        async_add_entities(
            [MeshtasticChannelNotify(coordinator, channel) for channel in channels]
            + [MeshtasticNodeNotify(coordinator, node) for node in nodes]
        )

    _check_targets()
    entry.async_on_unload(coordinator.async_add_listener(_check_targets))


class MeshtasticChannelNotify(MeshtasticEntity, NotifyEntity):
    """Broadcasts a text message on one channel of the gateway."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_translation_key = "channel"

    def __init__(
        self, coordinator: MeshtasticCoordinator, channel: MeshtasticChannel
    ) -> None:
        """Initialise the notify entity of one channel."""
        super().__init__(coordinator, f"channel_{channel.index}")
        self._channel_index = channel.index
        # The primary channel usually has no name at all; the index is the
        # only thing that tells two unnamed channels apart.
        display = channel.name or str(channel.index)
        self._attr_translation_placeholders = {"channel": display}
        self._target = f"channel {display}"

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Broadcast a message on this channel."""
        result = await self.coordinator.client.async_send_text(
            _body(message, title),
            destination=BROADCAST_NUM,
            channel_index=self._channel_index,
            want_ack=True,
        )
        raise_for_result(result, node=self._target)


class MeshtasticNodeNotify(MeshtasticNodeEntity, NotifyEntity):
    """Sends a direct message to one mesh node."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_translation_key = "direct_message"

    def __init__(
        self, coordinator: MeshtasticCoordinator, node: MeshtasticNode
    ) -> None:
        """Initialise the notify entity of one node."""
        super().__init__(coordinator, node, "direct_message")

    @property
    @override
    def available(self) -> bool:
        """Return True while this node can be messaged.

        A node that runs a firmware build without a text message module tells
        the mesh so; sending to it would only burn airtime.
        """
        if (node := self.node) is None or node.is_unmessagable:
            return False
        return super().available

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a direct message to this node and wait for its acknowledgement."""
        result = await self.coordinator.client.async_send_text(
            _body(message, title), destination=self.node_num, want_ack=True
        )
        node = self.node
        raise_for_result(result, node=self.node_id if node is None else node.name)
