"""Support for Meshtastic node positions."""

from collections.abc import Mapping
from typing import Any, Final, override

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
    TrackerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .const import (
    ATTR_LOCATION_SOURCE,
    ATTR_PRECISION_BITS,
    CONF_TRACK_POSITION,
    DEFAULT_TRACK_POSITION,
    DOMAIN,
    node_unique_id,
)
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import MeshtasticNode, Position

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

#: Unique-id suffix and translation key of every tracker this platform creates.
KEY_POSITION: Final = "position"

ATTR_ALTITUDE: Final = "altitude"


def _position_of(node: MeshtasticNode | None) -> Position | None:
    """Return a node's position, but only when it has usable coordinates."""
    if node is None or (position := node.position) is None or not position.valid:
        return None
    return position


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic device trackers from a config entry."""
    entity_registry = er.async_get(hass)
    if not entry.options.get(CONF_TRACK_POSITION, DEFAULT_TRACK_POSITION):
        # Tracking was switched off, so take the trackers an earlier run
        # created with it instead of leaving unavailable entities behind.
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.domain == DEVICE_TRACKER_DOMAIN:
                entity_registry.async_remove(entity.entity_id)
        return

    coordinator = entry.runtime_data.coordinator
    gateway = coordinator.gateway
    # Node number of every node that already has a tracker, keyed by node id,
    # so a node the mesh forgot can still be resolved back to its unique id.
    known: dict[str, int] = {}
    gateway_added = False

    @callback
    def _check_nodes() -> None:
        """Add trackers for nodes that have a position, drop forgotten ones."""
        nonlocal gateway_added
        nodes = coordinator.data.nodes
        entities: list[TrackerEntity] = []

        if not gateway_added and _position_of(nodes.get(gateway.node_id)) is not None:
            gateway_added = True
            entities.append(MeshtasticGatewayTracker(coordinator))

        for node_id in sorted(nodes.keys() - known.keys()):
            node = nodes[node_id]
            if (
                # The gateway is tracked on the gateway device itself, and a
                # node that has only ever been relayed is not worth a device.
                node_id == gateway.node_id
                or node.presumptive
                or _position_of(node) is None
            ):
                continue
            known[node_id] = node.num
            entities.append(MeshtasticNodeTracker(coordinator, node))

        if entities:
            async_add_entities(entities)

        if not coordinator.last_update_success or not coordinator.client.connected:
            # A node missing from the table while the link is down only means
            # Home Assistant lost sight of the mesh, not that the node is gone.
            return
        for node_id in known.keys() - nodes.keys():
            unique_id = node_unique_id(
                gateway.node_num, known.pop(node_id), KEY_POSITION
            )
            if entity_id := entity_registry.async_get_entity_id(
                DEVICE_TRACKER_DOMAIN, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)

    _check_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_check_nodes))


class MeshtasticTracker(TrackerEntity):
    """Rendering of a Meshtastic position, shared by both tracker flavours."""

    _attr_source_type = SourceType.GPS
    _attr_translation_key = KEY_POSITION

    @property
    def position(self) -> Position | None:
        """Return the position to render, or None when there is none."""
        raise NotImplementedError

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latitude of the node."""
        return position.latitude if (position := self.position) else None

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude of the node."""
        return position.longitude if (position := self.position) else None

    @property
    @override
    def location_accuracy(self) -> float:
        """Return the radius in metres that the reported position stands for.

        A node can be configured to blur its position by dropping low order
        bits of the coordinates, which makes the report a cell rather than a
        point.  ``0`` means the node reported at full precision.
        """
        return position.location_accuracy if (position := self.position) else 0

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the parts of the position that are not the coordinates."""
        if (position := self.position) is None:
            return None
        return {
            ATTR_ALTITUDE: position.altitude,
            ATTR_PRECISION_BITS: position.precision_bits,
            ATTR_LOCATION_SOURCE: position.location_source,
        }


class MeshtasticGatewayTracker(MeshtasticEntity, MeshtasticTracker):
    """Position of the node Home Assistant is connected to."""

    def __init__(self, coordinator: MeshtasticCoordinator) -> None:
        """Initialise the gateway tracker."""
        super().__init__(coordinator, KEY_POSITION)
        self._node_id = coordinator.gateway.node_id

    @property
    @override
    def position(self) -> Position | None:
        """Return the gateway's own position."""
        return _position_of(self.coordinator.data.nodes.get(self._node_id))


class MeshtasticNodeTracker(MeshtasticNodeEntity, MeshtasticTracker):
    """Position of one node of the mesh."""

    def __init__(
        self, coordinator: MeshtasticCoordinator, node: MeshtasticNode
    ) -> None:
        """Initialise a node tracker."""
        super().__init__(coordinator, node, KEY_POSITION)

    @property
    @override
    def position(self) -> Position | None:
        """Return the node's last reported position."""
        return _position_of(self.node)
