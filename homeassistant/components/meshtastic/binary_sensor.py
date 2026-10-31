"""Support for Meshtastic connectivity and node flags."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, override

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from . import MeshtasticConfigEntry
from .const import DOMAIN, NODE_ONLINE_SECONDS, node_unique_id
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import MeshtasticNode

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

KEY_CONNECTED: Final = "connected"
KEY_ONLINE: Final = "online"

#: A node not heard from within this window counts as offline, matching the
#: firmware's own ``NUM_ONLINE_SECS``.
ONLINE_WINDOW: Final = timedelta(seconds=NODE_ONLINE_SECONDS)


@dataclass(frozen=True, kw_only=True)
class MeshtasticNodeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Meshtastic node flag."""

    is_on_fn: Callable[[MeshtasticNode], bool]


NODE_FLAGS: Final[tuple[MeshtasticNodeBinarySensorEntityDescription, ...]] = (
    MeshtasticNodeBinarySensorEntityDescription(
        key="via_mqtt",
        translation_key="via_mqtt",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda node: node.via_mqtt,
    ),
    MeshtasticNodeBinarySensorEntityDescription(
        key="has_public_key",
        translation_key="has_public_key",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda node: node.has_public_key,
    ),
    MeshtasticNodeBinarySensorEntityDescription(
        key="key_manually_verified",
        translation_key="key_manually_verified",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda node: node.is_key_manually_verified,
    ),
    MeshtasticNodeBinarySensorEntityDescription(
        key="licensed",
        translation_key="licensed",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda node: node.is_licensed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    gateway = coordinator.gateway
    entity_registry = er.async_get(hass)
    async_add_entities([MeshtasticConnectivityBinarySensor(coordinator)])

    # Node number of every node this platform has already created entities for,
    # keyed by node id, so a node the mesh forgot can still be resolved back to
    # its unique ids.
    known: dict[str, int] = {}

    @callback
    def _check_nodes() -> None:
        """Add entities for newly discovered nodes and drop forgotten ones."""
        nodes = coordinator.data.nodes
        current = {
            node_id: node.num
            for node_id, node in nodes.items()
            # The gateway reports its own link state, and a node that has only
            # ever been relayed is not worth a device.
            if node_id != gateway.node_id and not node.presumptive
        }
        if new := sorted(current.keys() - known.keys()):
            known.update({node_id: current[node_id] for node_id in new})
            async_add_entities(
                entity
                for node_id in new
                for entity in _async_node_entities(coordinator, nodes[node_id])
            )

        if not coordinator.last_update_success or not coordinator.client.connected:
            # A node missing from the table while the link is down only means
            # Home Assistant lost sight of the mesh, not that the node is gone.
            return
        for node_id in known.keys() - nodes.keys():
            node_num = known.pop(node_id)
            for key in (KEY_ONLINE, *(flag.key for flag in NODE_FLAGS)):
                unique_id = node_unique_id(gateway.node_num, node_num, key)
                if entity_id := entity_registry.async_get_entity_id(
                    BINARY_SENSOR_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)

    _check_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_check_nodes))


@callback
def _async_node_entities(
    coordinator: MeshtasticCoordinator, node: MeshtasticNode
) -> list[BinarySensorEntity]:
    """Return every binary sensor of one mesh node."""
    return [
        MeshtasticNodeOnlineBinarySensor(coordinator, node),
        *(
            MeshtasticNodeFlagBinarySensor(coordinator, node, description)
            for description in NODE_FLAGS
        ),
    ]


class MeshtasticConnectivityBinarySensor(MeshtasticEntity, BinarySensorEntity):
    """Whether Home Assistant currently has a link to the gateway node."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = KEY_CONNECTED

    def __init__(self, coordinator: MeshtasticCoordinator) -> None:
        """Initialise the connectivity sensor."""
        super().__init__(coordinator, KEY_CONNECTED)

    @property
    @override
    def available(self) -> bool:
        """Return True always.

        This is the one entity that has to keep reporting while the link is
        down: going unavailable would hide the very state it exists to show.
        """
        return True

    @property
    @override
    def is_on(self) -> bool:
        """Return True while the TCP link to the gateway is up."""
        return self.coordinator.client.connected


class MeshtasticNodeOnlineBinarySensor(MeshtasticNodeEntity, BinarySensorEntity):
    """Whether the gateway heard from a node recently enough to call it online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = KEY_ONLINE

    def __init__(
        self, coordinator: MeshtasticCoordinator, node: MeshtasticNode
    ) -> None:
        """Initialise the online sensor."""
        super().__init__(coordinator, node, KEY_ONLINE)
        self._unsub_expiry: CALLBACK_TYPE | None = None

    @property
    @override
    def is_on(self) -> bool:
        """Return True while the node was heard within the online window."""
        if (node := self.node) is None or node.last_heard is None:
            return False
        return dt_util.utcnow() - node.last_heard < ONLINE_WINDOW

    @override
    async def async_added_to_hass(self) -> None:
        """Start watching for the moment this node goes stale."""
        await super().async_added_to_hass()
        self._async_schedule_expiry()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Drop the staleness timer so nothing outlives the entity."""
        self._async_cancel_expiry()
        await super().async_will_remove_from_hass()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Re-arm the staleness timer whenever the node was heard again."""
        self._async_schedule_expiry()
        super()._handle_coordinator_update()

    @callback
    def _async_cancel_expiry(self) -> None:
        """Cancel a pending staleness timer."""
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    @callback
    def _async_schedule_expiry(self) -> None:
        """Write the state again at the exact moment the node goes stale.

        Nothing pushes "this node went quiet", so the transition to ``off`` has
        to be scheduled.  One timer per node, re-armed only when the node is
        heard again, is far cheaper than polling every node every minute.
        """
        self._async_cancel_expiry()
        if (node := self.node) is None or node.last_heard is None:
            return
        expires_at = node.last_heard + ONLINE_WINDOW
        if expires_at <= dt_util.utcnow():
            return
        self._unsub_expiry = async_track_point_in_utc_time(
            self.hass, self._async_expired, expires_at
        )

    @callback
    def _async_expired(self, _now: datetime) -> None:
        """Publish the node as offline."""
        self._unsub_expiry = None
        self.async_write_ha_state()


class MeshtasticNodeFlagBinarySensor(MeshtasticNodeEntity, BinarySensorEntity):
    """One boolean flag the mesh reports about a node."""

    entity_description: MeshtasticNodeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        node: MeshtasticNode,
        description: MeshtasticNodeBinarySensorEntityDescription,
    ) -> None:
        """Initialise a node flag sensor."""
        super().__init__(coordinator, node, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the flag, or None once the node is gone."""
        if (node := self.node) is None:
            return None
        return self.entity_description.is_on_fn(node)
