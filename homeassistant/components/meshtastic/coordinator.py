"""Coordinator and node-registry persistence for the Meshtastic integration.

The coordinator runs in push mode: there is no polling, the client feeds it from
the radio and it republishes an immutable :class:`MeshtasticData` snapshot with
``async_set_updated_data``, which always notifies every listener.  Dampening is
therefore done where the change is known: the merge helpers below return False
when a packet or a node record left the table exactly as it was, and only a
real change is published.

Nodes are persisted in a per-entry ``Store`` so that node devices and their
entities survive a restart.  The save is debounced but cannot be starved: the
timer is armed once and never pushed out, and it is flushed on unload and on
``EVENT_HOMEASSISTANT_STOP``.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import MeshtasticClient, MeshtasticClientCallbacks
from .const import (
    DOMAIN,
    LOGGER,
    MAX_STORED_NODES,
    STORAGE_KEY_FORMAT,
    STORAGE_MINOR_VERSION,
    STORAGE_SAVE_DELAY,
    STORAGE_VERSION,
    format_node_id,
)
from .models import (
    GatewayInfo,
    MeshtasticData,
    MeshtasticNode,
    MeshtasticNotification,
    MeshtasticPacket,
    Position,
    PositionSource,
    TelemetrySample,
)

if TYPE_CHECKING:
    from .config_entity import MeshtasticConfigSnapshot


@dataclass(slots=True)
class MeshtasticRuntimeData:
    """Everything the config entry owns at runtime."""

    client: MeshtasticClient
    coordinator: MeshtasticCoordinator
    #: The gateway's configuration, shared by the platforms that expose it and
    #: created by whichever of them sets up first.  It holds the coordinator,
    #: the client and a lock, so it belongs to the entry: ``runtime_data`` is
    #: dropped on unload, and the snapshot goes with it.
    config_snapshot: MeshtasticConfigSnapshot | None = None


#: The config entry type, defined here rather than in ``__init__`` so that a
#: module ``__init__`` imports at module level - ``services``, ``config_entity``
#: - can name it without importing the package back while it is still loading.
#: ``__init__`` re-exports it, which is the name platforms import.
type MeshtasticConfigEntry = ConfigEntry[MeshtasticRuntimeData]


class MeshtasticNodeStore(Store[dict[str, Any]]):
    """Versioned store for the node table of one config entry."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate stored node data to the current schema.

        Within major version 1 every record is simply re-parsed, which drops
        keys we no longer know and fills in defaults for keys that were added.
        An unknown major version fails loudly rather than silently truncating
        the user's node history.
        """
        if old_major_version > STORAGE_VERSION:
            raise NotImplementedError
        if old_major_version == 1:
            nodes = old_data.get("nodes")
            migrated: dict[str, Any] = {}
            if isinstance(nodes, dict):
                for node_id, record in nodes.items():
                    if not isinstance(record, dict):
                        continue
                    if (node := MeshtasticNode.from_dict(record)) is not None:
                        migrated[node_id] = node.as_dict()
                    else:
                        LOGGER.warning("Dropping unreadable stored node %s", node_id)
            return {"nodes": migrated}
        raise NotImplementedError


class MeshtasticNodeRegistry:
    """Debounced, starvation-proof persistence of the node table."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the registry for one config entry."""
        self.hass = hass
        self._store = MeshtasticNodeStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_FORMAT.format(entry_id=entry_id),
            minor_version=STORAGE_MINOR_VERSION,
            atomic_writes=True,
        )
        self._data_func: Callable[[], dict[str, MeshtasticNode]] | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_stop: CALLBACK_TYPE | None = None
        self._closed = False

    async def async_load(self) -> dict[str, MeshtasticNode]:
        """Load the persisted node table."""
        stored = await self._store.async_load()
        if not stored:
            return {}
        raw_nodes = stored.get("nodes")
        if not isinstance(raw_nodes, dict):
            return {}
        nodes: dict[str, MeshtasticNode] = {}
        for node_id, record in raw_nodes.items():
            if (
                isinstance(record, dict)
                and (node := MeshtasticNode.from_dict(record)) is not None
            ):
                nodes[node_id] = node
        return nodes

    @callback
    def async_schedule_save(
        self, data_func: Callable[[], dict[str, MeshtasticNode]]
    ) -> None:
        """Arm the save timer once; never push an armed timer out.

        ``Store.async_delay_save`` reschedules on every call, so under steady
        mesh traffic it would never fire.  Arming once bounds the loss to
        ``STORAGE_SAVE_DELAY`` seconds no matter how busy the mesh is.

        Once the registry is closed nothing is armed again: a packet that
        arrives while the entry unloads, or after Home Assistant announced the
        shutdown, must not leave a timer behind that nobody will cancel.
        """
        if self._closed:
            return
        self._data_func = data_func
        if self._unsub_stop is None:
            self._unsub_stop = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
            )
        if self._unsub_timer is not None:
            return
        self._unsub_timer = async_call_later(
            self.hass, STORAGE_SAVE_DELAY, self._async_timer_fired
        )

    @callback
    def _async_timer_fired(self, _now: datetime) -> None:
        """Write the pending snapshot when the debounce elapsed."""
        self._unsub_timer = None
        self.hass.async_create_task(
            self.async_flush(), name=f"{DOMAIN} save nodes", eager_start=True
        )

    async def _async_handle_stop(self, _event: Event) -> None:
        """Flush on Home Assistant shutdown; entries are not unloaded then.

        The armed timer has to go with it.  ``async_call_later`` schedules a
        real event-loop timer, and one that outlives the shutdown keeps the
        loop from closing cleanly.
        """
        self._unsub_stop = None
        self._async_close()
        await self.async_flush()

    async def async_flush(self) -> None:
        """Write the current snapshot now, if there is anything to write."""
        if self._data_func is None:
            return
        data_func, self._data_func = self._data_func, None
        await self._store.async_save(
            {
                "nodes": {
                    node_id: node.as_dict() for node_id, node in data_func().items()
                }
            }
        )

    @callback
    def _async_close(self) -> None:
        """Disarm the save timer and drop the shutdown hook, once and for all."""
        self._closed = True
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None

    async def async_shutdown(self) -> None:
        """Cancel the timer, flush what is pending and drop the stop hook."""
        self._async_close()
        await self.async_flush()

    async def async_remove(self) -> None:
        """Delete the persisted node table."""
        self._async_close()
        self._data_func = None
        await self._store.async_remove()


class MeshtasticCoordinator(DataUpdateCoordinator[MeshtasticData]):
    """Push coordinator holding the gateway identity and the node table."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: MeshtasticClient,
    ) -> None:
        """Initialise the coordinator and wire the client's callbacks to it."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.client = client
        self.registry = MeshtasticNodeRegistry(hass, config_entry.entry_id)
        self._nodes: dict[str, MeshtasticNode] = {}
        self._gateway: GatewayInfo | None = None
        self._packet_listeners: list[Callable[[MeshtasticPacket], None]] = []
        client.callbacks = MeshtasticClientCallbacks(
            connected=self.async_handle_connected,
            disconnected=self.async_handle_disconnected,
            packet=self.async_handle_packet,
            node_updated=self.async_handle_node_updated,
            notification=self.async_handle_notification,
        )

    # -- lifecycle --------------------------------------------------------

    async def async_load_stored_nodes(self) -> None:
        """Populate the node table from the store, before the first connect."""
        self._nodes = await self.registry.async_load()

    @override
    async def async_shutdown(self) -> None:
        """Flush the node table and stop the coordinator."""
        await self.registry.async_shutdown()
        await super().async_shutdown()

    # -- accessors --------------------------------------------------------

    @property
    def gateway(self) -> GatewayInfo:
        """Return the gateway identity.

        Only valid after ``async_setup_entry`` connected once; entities are not
        created before that.
        """
        if self._gateway is None:
            raise RuntimeError("Meshtastic gateway information is not available yet")
        return self._gateway

    @property
    def gateway_or_none(self) -> GatewayInfo | None:
        """Return the gateway identity, or None if never connected."""
        return self._gateway

    @property
    def nodes(self) -> dict[str, MeshtasticNode]:
        """Return the current node table, keyed by ``!xxxxxxxx`` node id."""
        return self._nodes

    def get_node(self, node_id: str) -> MeshtasticNode | None:
        """Return one node by id."""
        return self._nodes.get(node_id)

    @callback
    def async_add_packet_listener(
        self, listener: Callable[[MeshtasticPacket], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to every received packet.

        Platforms that care about traffic rather than state (message events,
        for instance) use this instead of the coordinator's data listener.
        """
        self._packet_listeners.append(listener)

        @callback
        def _remove() -> None:
            self._packet_listeners.remove(listener)

        return _remove

    # -- client callbacks (event loop) ------------------------------------

    @callback
    def async_handle_connected(self, gateway: GatewayInfo) -> None:
        """Handle a completed handshake with the gateway node."""
        self._gateway = gateway
        now = dt_util.utcnow()
        existing = self._nodes.get(gateway.node_id)
        self._nodes[gateway.node_id] = replace(
            existing
            or MeshtasticNode(
                num=gateway.node_num, node_id=gateway.node_id, first_seen=now
            ),
            num=gateway.node_num,
            node_id=gateway.node_id,
            long_name=gateway.long_name,
            short_name=gateway.short_name,
            hardware_model=gateway.hardware_model,
            role=gateway.role,
            hops_away=0,
            last_heard=now,
            presumptive=False,
        )
        self._async_publish()

    @callback
    def async_handle_disconnected(self, reason: str) -> None:
        """Handle the link going away, or the reason for it changing."""
        self.async_set_update_error(UpdateFailed(reason))
        # ``async_set_update_error`` only notifies on the transition out of a
        # good state, but the link keeps changing while it is down -- an
        # ordinary reconnect becomes a paused one when the circuit breaker
        # opens -- and the repair issues key off exactly that.
        self.async_update_listeners()

    @callback
    def async_handle_packet(self, packet: MeshtasticPacket) -> None:
        """Merge a received packet into the node table and fan it out."""
        if self._async_merge_packet(packet):
            self._async_publish()
        for listener in list(self._packet_listeners):
            listener(packet)

    @callback
    def async_handle_node_updated(self, node: MeshtasticNode) -> None:
        """Merge a node-DB record pushed by the gateway."""
        if self._async_merge_node(node):
            self._async_publish()

    @callback
    def async_handle_notification(self, notification: MeshtasticNotification) -> None:
        """Log a firmware notification; requests pick it up via the tracker."""
        LOGGER.debug("Notification from %s: %s", self.client.host, notification.message)

    # -- merging ----------------------------------------------------------

    @callback
    def _async_publish(self) -> None:
        """Publish a new snapshot and arm the persistence timer."""
        if self._gateway is None:
            return
        self._async_enforce_bound()
        self.async_set_updated_data(
            MeshtasticData(gateway=self._gateway, nodes=dict(self._nodes))
        )
        self.registry.async_schedule_save(lambda: self._nodes)

    def _async_merge_packet(self, packet: MeshtasticPacket) -> bool:
        """Merge one packet; return True when the node table changed."""
        node_id = packet.from_id or format_node_id(packet.from_num)
        now = packet.received_at or dt_util.utcnow()
        heard = dt_util.utc_from_timestamp(packet.rx_time) if packet.rx_time else now
        current = self._nodes.get(node_id) or MeshtasticNode(
            num=packet.from_num, node_id=node_id, first_seen=now
        )
        changes: dict[str, Any] = {
            "last_heard": heard,
            "last_heard_device": packet.rx_time or current.last_heard_device,
            "channel": packet.channel or current.channel,
            "via_mqtt": packet.via_mqtt,
        }
        if packet.rx_snr is not None:
            changes["snr"] = packet.rx_snr
        if packet.rx_rssi is not None:
            changes["rssi"] = packet.rx_rssi
        if (hops := packet.hops_away) is not None:
            changes["hops_away"] = hops
        if (user := packet.user) is not None:
            changes |= {
                "node_id": user.node_id,
                "long_name": user.long_name or current.long_name,
                "short_name": user.short_name or current.short_name,
                "hardware_model": user.hardware_model or current.hardware_model,
                "role": user.role or current.role,
                "is_licensed": user.is_licensed,
                "is_unmessagable": user.is_unmessagable,
                "has_public_key": user.has_public_key,
                "presumptive": False,
            }
        if (position := packet.position) is not None and _is_newer(
            position, current.position
        ):
            changes["position"] = position
        if (sample := packet.telemetry) is not None:
            telemetry = dict(current.telemetry)
            telemetry[str(sample.family)] = sample
            changes["telemetry"] = telemetry
        updated = replace(current, **changes)
        if updated == current:
            return False
        self._nodes.pop(node_id, None)
        self._nodes[updated.node_id] = updated
        return True

    def _async_merge_node(self, node: MeshtasticNode) -> bool:
        """Merge a node-DB record; return True when the node table changed."""
        current = self._nodes.get(node.node_id)
        if current is None:
            self._nodes[node.node_id] = node
            return True
        changes: dict[str, Any] = {
            "is_favorite": node.is_favorite,
            "is_ignored": node.is_ignored,
            "is_muted": node.is_muted,
            "is_key_manually_verified": node.is_key_manually_verified,
        }
        if not node.presumptive:
            changes |= {
                "long_name": node.long_name or current.long_name,
                "short_name": node.short_name or current.short_name,
                "hardware_model": node.hardware_model or current.hardware_model,
                "role": node.role or current.role,
                "is_licensed": node.is_licensed,
                "is_unmessagable": node.is_unmessagable,
                "has_public_key": node.has_public_key,
                "presumptive": False,
            }
        if node.hops_away is not None:
            changes["hops_away"] = node.hops_away
        if node.snr is not None:
            changes["snr"] = node.snr
        if node.last_heard is not None and (
            current.last_heard is None or node.last_heard > current.last_heard
        ):
            changes["last_heard"] = node.last_heard
            changes["last_heard_device"] = node.last_heard_device
        if node.position is not None and _is_newer(node.position, current.position):
            changes["position"] = node.position
        if node.telemetry:
            telemetry = dict(current.telemetry)
            for family, sample in node.telemetry.items():
                if _is_newer_sample(sample, telemetry.get(family)):
                    telemetry[family] = sample
            changes["telemetry"] = telemetry
        updated = replace(current, **changes)
        if updated == current:
            return False
        self._nodes[node.node_id] = updated
        return True

    @callback
    def _async_enforce_bound(self) -> None:
        """Evict the least recently heard nodes above ``MAX_STORED_NODES``."""
        if len(self._nodes) <= MAX_STORED_NODES:
            return
        gateway_id = self._gateway.node_id if self._gateway else None
        candidates = [
            node
            for node in self._nodes.values()
            if node.node_id != gateway_id
            and not node.is_favorite
            and not node.is_ignored
        ]
        candidates.sort(
            key=lambda node: (
                node.last_heard or node.first_seen or dt_util.utc_from_timestamp(0)
            )
        )
        for node in candidates[: len(self._nodes) - MAX_STORED_NODES]:
            self._nodes.pop(node.node_id, None)


def _is_newer(candidate: Position, current: Position | None) -> bool:
    """Return True when a position should replace the stored one."""
    if current is None:
        return True
    if (
        candidate.device_time is not None
        and current.device_time is not None
        and candidate.device_time != current.device_time
    ):
        return candidate.device_time > current.device_time
    return not (
        candidate.source is PositionSource.NODE_INFO
        and current.source is PositionSource.PACKET
    )


def _is_newer_sample(
    candidate: TelemetrySample, current: TelemetrySample | None
) -> bool:
    """Return True when a telemetry sample should replace the stored one."""
    if current is None:
        return True
    if candidate.device_time is not None and current.device_time is not None:
        return candidate.device_time >= current.device_time
    return True
