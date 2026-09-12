"""Support for Meshtastic text messages as events."""

from typing import Final, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .const import ATTR_BACKLOG, format_node_id
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import MeshtasticMessage, MeshtasticNode, MeshtasticPacket

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

EVENT_TYPE_MESSAGE: Final = "message"
EVENT_TYPE_DIRECT_MESSAGE: Final = "direct_message"

#: Keys of ``MeshtasticMessage.as_dict()`` that carry a different value for
#: every single message.  Recording them would write one more row into the
#: recorder's attribute table per message received, so they are kept out of it;
#: they are still in the live state and in the payload automations see.
_VOLATILE_ATTRIBUTES: Final = frozenset(
    {
        "hops_away",
        "packet_id",
        "received_at",
        "reply_id",
        "rx_rssi",
        "rx_snr",
        "rx_time",
        "text",
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic message events from a config entry."""
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def _check_nodes() -> None:
        gateway_num = coordinator.data.gateway.node_num
        new = {
            node_id
            for node_id, node in coordinator.data.nodes.items()
            if node_id not in known
            and not node.presumptive
            # The gateway has its own event entity on the gateway device.
            and node.num != gateway_num
        }
        if not new:
            return
        known.update(new)
        async_add_entities(
            MeshtasticNodeMessageEvent(coordinator, coordinator.data.nodes[node_id])
            for node_id in new
        )

    async_add_entities([MeshtasticGatewayMessageEvent(coordinator)])
    _check_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_check_nodes))


class MeshtasticMessageEvent(EventEntity):
    """Shared behaviour of the Meshtastic message event entities.

    This is mixed in front of :class:`EventEntity` by entities that are also
    coordinator entities, which is where ``coordinator`` comes from.
    """

    _attr_event_types = [EVENT_TYPE_MESSAGE, EVENT_TYPE_DIRECT_MESSAGE]
    _attr_translation_key = "message"
    _unrecorded_attributes = _VOLATILE_ATTRIBUTES

    coordinator: MeshtasticCoordinator

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to received traffic.

        Messages are traffic, not state, so they come from the client's packet
        stream rather than from the coordinator's data updates.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_packet_listener(self._async_handle_packet)
        )

    @callback
    def _accepts(self, packet: MeshtasticPacket) -> bool:
        """Return True when this entity reports the given packet."""
        return True

    @callback
    def _async_handle_packet(self, packet: MeshtasticPacket) -> None:
        """Fire an event for a received text message."""
        if packet.backlog or not self._accepts(packet):
            # A node replays everything it queued while Home Assistant was
            # away as soon as the connection is back.  Firing those would
            # re-run automations for messages the user has long since read.
            return
        node = self.coordinator.get_node(
            packet.from_id or format_node_id(packet.from_num)
        )
        message = MeshtasticMessage.from_packet(
            packet, from_name=None if node is None else node.name
        )
        if message is None:
            return
        attributes = message.as_dict()
        # Every event fired is live traffic, so the flag is always False here.
        del attributes[ATTR_BACKLOG]
        self._trigger_event(
            EVENT_TYPE_MESSAGE if message.is_broadcast else EVENT_TYPE_DIRECT_MESSAGE,
            attributes,
        )
        self.async_write_ha_state()


class MeshtasticGatewayMessageEvent(MeshtasticEntity, MeshtasticMessageEvent):
    """Fires for every text message the gateway hears."""

    def __init__(self, coordinator: MeshtasticCoordinator) -> None:
        """Initialise the gateway message event entity."""
        super().__init__(coordinator, "message")


class MeshtasticNodeMessageEvent(MeshtasticNodeEntity, MeshtasticMessageEvent):
    """Fires for the text messages sent by one mesh node."""

    def __init__(
        self, coordinator: MeshtasticCoordinator, node: MeshtasticNode
    ) -> None:
        """Initialise the message event entity of one node."""
        super().__init__(coordinator, node, "message")

    @callback
    @override
    def _accepts(self, packet: MeshtasticPacket) -> bool:
        """Return True for the packets this node sent."""
        return packet.from_num == self.node_num
