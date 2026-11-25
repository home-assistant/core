"""Matter to Home Assistant adapter."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from matter_server.client.models.device_types import BridgedNode
from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import Undefined

from .const import DOMAIN, ID_TYPE_DEVICE_ID, ID_TYPE_SERIAL, LOGGER
from .discovery import async_discover_entities
from .helpers import (
    MatterConfigEntry,
    endpoint_requires_child_device,
    get_child_device_identifier,
    get_child_device_names,
    get_child_device_owner,
    get_device_endpoint,
    get_device_id,
    get_device_id_from_identifiers,
    get_discovery_key,
    get_entity_unique_id,
    get_legacy_device_id,
    get_node_device_identifier,
    get_power_topology_endpoint_id,
)
from .util import get_clean_name

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

    from .models import MatterEntityInfo
    from .semantic_tags import ChildDeviceName

# The endpoint whose child device holds an endpoint's entities, with the child's
# name, or None for both when they are on the node (or bridged) device.
type ChildDevicePlacement = tuple[int | None, ChildDeviceName | None]


def _get_child_device_placement(endpoint: MatterEndpoint) -> ChildDevicePlacement:
    """Return where the entities of the endpoint belong."""
    if (owner := get_child_device_owner(endpoint)) is None:
        return (None, None)
    return (
        owner.endpoint_id,
        get_child_device_names(endpoint.node).get(owner.endpoint_id),
    )


def _get_child_device_endpoint_ids(node: MatterNode, endpoint_id: int) -> set[int]:
    """Return the endpoints whose entities can be on the endpoint's child device.

    This doesn't depend on the endpoint still splitting, as the entities keep the
    device they were created on.
    """
    return {
        endpoint_id,
        *node.get_compose_child_ids(endpoint_id),
        *(
            other.endpoint_id
            for other in node.endpoints.values()
            if get_power_topology_endpoint_id(other) == endpoint_id
        ),
    }


# Recorded as the owner of moved entities that still have their child device
# names. It never equals a current placement, so the next owner check reloads.
_RENAME_PENDING: ChildDevicePlacement = (-1, None)


def _get_endpoint_and_part_ids(node: MatterNode, endpoint_id: int) -> set[int]:
    """Return the endpoint's ID with the IDs of its parts, at any depth.

    Unlike `get_compose_child_ids`, this also works for a part that is itself
    below another part.
    """
    endpoint_ids = {endpoint_id}
    for other_id in node.endpoints:
        seen = {other_id}
        parent = node.get_closest_compose_parent(other_id)
        while parent is not None and parent.endpoint_id not in seen:
            if parent.endpoint_id == endpoint_id:
                endpoint_ids.add(other_id)
                break
            seen.add(parent.endpoint_id)
            parent = node.get_closest_compose_parent(parent.endpoint_id)
    return endpoint_ids


def _get_unique_id_prefixes(
    server_info: ServerInfoMessage, node: MatterNode, endpoint_ids: Iterable[int]
) -> tuple[str, ...]:
    """Return the unique_id prefixes of the entities of the endpoints."""
    return tuple(
        f"{get_device_id(server_info, node.endpoints[endpoint_id])}-{endpoint_id}-"
        for endpoint_id in endpoint_ids
        if endpoint_id in node.endpoints
    )


def _move_entity_to_node_device(
    entity_registry: er.EntityRegistry,
    entity_entry: er.RegistryEntry,
    child_device: dr.ChildDeviceEntry,
    node_device_id: str,
) -> None:
    """Move an entity of a child device to the node device.

    Moving an entity disabled with its device would enable it, so the entities of
    a child device the user disabled stay disabled by the user.
    """
    disabled_by: er.RegistryEntryDisabler | Undefined = Undefined
    if (
        entity_entry.disabled_by is er.RegistryEntryDisabler.DEVICE
        and child_device.disabled_by is dr.DeviceEntryDisabler.USER
    ):
        disabled_by = er.RegistryEntryDisabler.USER
    entity_registry.async_update_entity(
        entity_entry.entity_id, device_id=node_device_id, disabled_by=disabled_by
    )


def _child_device_unique_id_prefix(child_device: dr.ChildDeviceEntry) -> str | None:
    """Return the unique_id prefix of the entities of a child device's endpoint."""
    if (device_id := get_device_id_from_identifiers(child_device)) is None:
        return None
    return f"{device_id}-"


def _child_device_endpoint_id(child_device: dr.ChildDeviceEntry) -> int | None:
    """Return the endpoint id encoded in a child device's Matter identifier."""
    if (device_id := get_device_id_from_identifiers(child_device)) is None:
        return None
    endpoint_part = device_id.rsplit("-", 1)[-1]
    return int(endpoint_part) if endpoint_part.isdigit() else None


def get_suggested_area(endpoint: MatterEndpoint) -> str | None:
    """Return the Matter Actions cluster Room name for the endpoint's device.

    A bridge (e.g. a Hue Bridge) advertises its rooms as EndpointListStruct entries of
    type Room on the Actions cluster, wherever it exposes that cluster, each listing the
    bridged endpoints in that room. Returns None rather than guessing when the endpoint
    is in no room, or in more than one with conflicting names.
    """
    candidate_ids = {
        endpoint.endpoint_id,
        *endpoint.node.get_compose_child_ids(endpoint.endpoint_id),
    }
    room_names: set[str] = set()
    for action_endpoint in endpoint.node.endpoints.values():
        actions = action_endpoint.get_cluster(clusters.Actions)
        if actions is None:
            continue
        for endpoint_list in actions.endpointLists:
            if endpoint_list.type != clusters.Actions.Enums.EndpointListTypeEnum.kRoom:
                continue
            if not candidate_ids & set(endpoint_list.endpoints or ()):
                continue
            if room_name := get_clean_name(endpoint_list.name):
                room_names.add(room_name)
    if len(room_names) == 1:
        return room_names.pop()
    return None


class MatterAdapter:
    """Connect Matter into Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        matter_client: MatterClient,
        config_entry: MatterConfigEntry,
    ) -> None:
        """Initialize the adapter."""
        self.matter_client = matter_client
        self.hass = hass
        self.config_entry = config_entry
        self.platform_handlers: dict[Platform, AddEntitiesCallback] = {}
        # Kept per endpoint so a re-added endpoint's entities are rediscovered.
        self.discovered_entities: dict[tuple[int, int], set[str]] = {}
        # Placement at entity creation, compared later to detect a needed reload.
        self._child_device_owners: dict[tuple[int, int], ChildDevicePlacement] = {}
        self._reload_scheduled = False

    def register_platform_handler(
        self, platform: Platform, add_entities: AddEntitiesCallback
    ) -> None:
        """Register a platform handler."""
        self.platform_handlers[platform] = add_entities

    async def setup_nodes(self) -> None:
        """Set up all existing nodes and subscribe to new nodes."""
        for node in self.matter_client.get_nodes():
            self._setup_node(node)

        def node_added_callback(event: EventType, node: MatterNode) -> None:
            """Handle node added event."""
            self._setup_node(node)

        def node_updated_callback(event: EventType, node: MatterNode) -> None:
            """Handle node updated event."""
            if not node.available:
                return
            # We always run the discovery logic again,
            # because the firmware version could have been changed or features added.
            self._setup_node(node)

        def endpoint_added_callback(event: EventType, data: dict[str, int]) -> None:
            """Handle endpoint added event."""
            node = self.matter_client.get_node(data["node_id"])
            endpoint = node.endpoints[data["endpoint_id"]]
            # Ensure the bridge device (endpoint 0) is registered before a
            # bridged child endpoint resolves it as its via_device.
            device_endpoint = get_device_endpoint(endpoint)
            if (
                device_endpoint.is_bridged_device
                and node.endpoints[0] != device_endpoint
            ):
                self._setup_endpoint(node.endpoints[0])
            self._setup_endpoint(endpoint)
            self._reload_if_child_device_owners_changed(node)

        def endpoint_removed_callback(event: EventType, data: dict[str, int]) -> None:
            """Handle endpoint removed event."""
            server_info = cast(ServerInfoMessage, self.matter_client.server_info)
            try:
                node = self.matter_client.get_node(data["node_id"])
            except KeyError:
                return  # race condition
            device_registry = dr.async_get(self.hass)
            endpoint = node.endpoints.get(data["endpoint_id"])
            if not endpoint:
                return  # race condition
            if get_device_endpoint(endpoint) != endpoint:
                # A composed device is represented by a single HA device, which is
                # only removed once its compose parent endpoint is removed. Parts
                # are removed before their parent, which then no longer finds them.
                self._remove_endpoint_entities(node, endpoint)
                return
            # An endpoint split into its own child device is removed on its own,
            # without touching the node (parent) device.
            child_identifier = get_child_device_identifier(server_info, endpoint)
            if child_device := device_registry.async_get_child_device_by_identifier(
                child_identifier, self.config_entry.entry_id
            ):
                self._remove_child_device(node, endpoint, child_device)
                return
            if endpoint.endpoint_id != 0 and not endpoint.is_bridged_device:
                # The device of any other endpoint is shared with the remaining
                # endpoints, so only the endpoint's own entities are removed.
                self._remove_endpoint_entities(node, endpoint)
                return
            node_device_id = get_device_id(server_info, endpoint)
            identifier = (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")
            if device := device_registry.async_get_device_by_identifier(
                identifier, self.config_entry.entry_id
            ):
                device_registry.async_remove_device(device.id)
            self._forget_endpoint_entities(
                node.node_id,
                {
                    endpoint.endpoint_id,
                    *node.get_compose_child_ids(endpoint.endpoint_id),
                },
            )

        def node_removed_callback(event: EventType, node_id: int) -> None:
            """Handle node removed event."""
            try:
                node = self.matter_client.get_node(node_id)
            except KeyError:
                return  # race condition
            for endpoint_id in node.endpoints:
                endpoint_removed_callback(
                    EventType.ENDPOINT_REMOVED,
                    {"node_id": node_id, "endpoint_id": endpoint_id},
                )

        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=endpoint_added_callback, event_filter=EventType.ENDPOINT_ADDED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=endpoint_removed_callback,
                event_filter=EventType.ENDPOINT_REMOVED,
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_removed_callback, event_filter=EventType.NODE_REMOVED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_added_callback, event_filter=EventType.NODE_ADDED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_updated_callback, event_filter=EventType.NODE_UPDATED
            )
        )

    def _setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        LOGGER.debug("Setting up entities for node %s", node.node_id)
        # Entities of a node set up before (e.g. on node update) are already live.
        node_was_set_up = any(
            node_id == node.node_id for node_id, _ in self.discovered_entities
        )
        try:
            # Prune first, so the entities of a removed child device are
            # rediscovered right away.
            self._prune_node_child_devices(node, node_was_set_up)
            # Process endpoints in order so the bridge device (endpoint 0) is
            # registered before any bridged child endpoint resolves it as its
            # via_device.
            for endpoint_id in sorted(node.endpoints):
                # Node endpoints are translated into HA devices
                self._setup_endpoint(node.endpoints[endpoint_id])
            self._reload_if_child_device_owners_changed(node)
        except Exception as err:  # noqa: BLE001
            # We don't want to crash the whole setup when a single node fails to setup
            # for whatever reason, so we catch all exceptions here.
            LOGGER.exception(
                "Error setting up node %s: %s",
                node.node_id,
                err,
            )

    def _prune_node_child_devices(
        self, node: MatterNode, node_was_set_up: bool
    ) -> None:
        """Remove child devices of a node that no longer map to a split endpoint.

        When the set of endpoints changes, a child device can become stale in two
        ways. If its endpoint still exists but no longer needs its own device (e.g.
        a sibling output was removed so it no longer collides), its entities are
        moved back to the node device to preserve user customizations. If its
        endpoint is gone entirely, the child device is removed together with its
        now-orphaned entities.

        Entities created on a child device have no name suffix. When live entities
        are moved back to the node device, the config entry is reloaded so they are
        recreated with the suffixed names of endpoints that don't split. During the
        first setup of a node its entities are created after the split changed, so
        no reload is needed.
        """
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        device_registry = dr.async_get(self.hass)
        node_device = device_registry.async_get_device_by_identifier(
            get_node_device_identifier(server_info, node.node_id),
            self.config_entry.entry_id,
        )
        if node_device is None:
            return
        expected_child_identifiers: set[tuple[str, str]] = set()
        current_child_identifiers: set[tuple[str, str]] = set()
        for endpoint in node.endpoints.values():
            child_identifier = get_child_device_identifier(server_info, endpoint)
            current_child_identifiers.add(child_identifier)
            if endpoint_requires_child_device(endpoint):
                expected_child_identifiers.add(child_identifier)
        entity_registry = er.async_get(self.hass)
        node_unique_id_prefix = f"{get_device_id(server_info, node.endpoints[0])}-"
        current_unique_id_prefixes = _get_unique_id_prefixes(
            server_info, node, node.endpoints
        )
        moved_entities = False
        for child_device in dr.async_entries_for_parent_device(
            device_registry, node_device.id
        ):
            if child_device.identifiers & expected_child_identifiers:
                continue
            endpoint_id = _child_device_endpoint_id(child_device)
            if child_device.identifiers & current_child_identifiers:
                # Include disabled entities so their customizations are kept.
                for entity_entry in er.async_entries_for_device(
                    entity_registry, child_device.id, include_disabled_entities=True
                ):
                    # Entities of an endpoint that vanished while unloaded, e.g. a
                    # Power Topology measurement endpoint, aren't moved.
                    if entity_entry.unique_id.startswith(
                        node_unique_id_prefix
                    ) and not entity_entry.unique_id.startswith(
                        current_unique_id_prefixes
                    ):
                        entity_registry.async_remove(entity_entry.entity_id)
                        continue
                    _move_entity_to_node_device(
                        entity_registry, entity_entry, child_device, node_device.id
                    )
                    # Disabled entities have no live entity object to rename.
                    if entity_entry.disabled_by is None:
                        moved_entities = True
                if endpoint_id is not None:
                    self._set_moved_to_node_device(
                        node.node_id, _get_child_device_endpoint_ids(node, endpoint_id)
                    )
            elif endpoint_id is not None:
                self._forget_endpoint_entities(
                    node.node_id, _get_child_device_endpoint_ids(node, endpoint_id)
                )
                # Entities of the gone endpoint placed on the node device, like
                # those of a vendor cluster covering the node, aren't removed
                # with the child device.
                if unique_id_prefix := _child_device_unique_id_prefix(child_device):
                    for entity_entry in er.async_entries_for_device(
                        entity_registry, node_device.id, include_disabled_entities=True
                    ):
                        if entity_entry.unique_id.startswith(unique_id_prefix):
                            entity_registry.async_remove(entity_entry.entity_id)
            device_registry.async_remove_device(child_device.id)
        if moved_entities and node_was_set_up:
            self._schedule_reload()

    def _set_moved_to_node_device(
        self, node_id: int, endpoint_ids: Iterable[int]
    ) -> None:
        """Record that the entities of the endpoints were moved to the node device."""
        for endpoint_id in endpoint_ids:
            if (key := (node_id, endpoint_id)) in self._child_device_owners:
                self._child_device_owners[key] = (None, None)

    def _set_rename_pending(self, node_id: int, endpoint_ids: Iterable[int]) -> None:
        """Record that live entities of the endpoints keep their child names."""
        for endpoint_id in endpoint_ids:
            if (key := (node_id, endpoint_id)) in self._child_device_owners:
                self._child_device_owners[key] = _RENAME_PENDING

    def _remove_child_device(
        self,
        node: MatterNode,
        endpoint: MatterEndpoint,
        child_device: dr.ChildDeviceEntry,
    ) -> None:
        """Remove an endpoint's child device with the endpoint's entities.

        Entities of other endpoints on it, e.g. of a Power Topology measurement
        endpoint, stay and are moved to the node device. As they were created
        without a name suffix, they are recorded as pending a rename, so the
        owner check after the node update that follows the removal reloads the
        config entry to recreate them with the names of the node device, unless
        their endpoint is removed by then too.
        """
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        endpoint_ids = {
            endpoint.endpoint_id,
            *node.get_compose_child_ids(endpoint.endpoint_id),
        }
        unique_id_prefixes = _get_unique_id_prefixes(server_info, node, endpoint_ids)
        other_endpoint_ids = (
            _get_child_device_endpoint_ids(node, endpoint.endpoint_id) - endpoint_ids
        )
        other_unique_id_prefixes = {
            other_id: _get_unique_id_prefixes(server_info, node, (other_id,))
            for other_id in other_endpoint_ids
        }
        if node_device := device_registry.async_get_device_by_identifier(
            get_node_device_identifier(server_info, node.node_id),
            self.config_entry.entry_id,
        ):
            live_endpoint_ids: set[int] = set()
            for entity_entry in er.async_entries_for_device(
                entity_registry, child_device.id, include_disabled_entities=True
            ):
                if not entity_entry.unique_id.startswith(unique_id_prefixes):
                    _move_entity_to_node_device(
                        entity_registry, entity_entry, child_device, node_device.id
                    )
                    # Disabled entities have no live entity object to rename.
                    if entity_entry.disabled_by is None:
                        live_endpoint_ids.update(
                            other_id
                            for other_id, prefixes in other_unique_id_prefixes.items()
                            if entity_entry.unique_id.startswith(prefixes)
                        )
            self._set_moved_to_node_device(
                node.node_id, other_endpoint_ids - live_endpoint_ids
            )
            self._set_rename_pending(node.node_id, live_endpoint_ids)
        # Remove the endpoint's entities by their unique ID, so also any that are
        # not on the child device.
        self._remove_endpoint_entities(node, endpoint)
        device_registry.async_remove_device(child_device.id)

    def _forget_endpoint_entities(
        self, node_id: int, endpoint_ids: Iterable[int]
    ) -> None:
        """Drop endpoints' discovery keys so their entities can be rediscovered."""
        for endpoint_id in endpoint_ids:
            self.discovered_entities.pop((node_id, endpoint_id), None)
            self._child_device_owners.pop((node_id, endpoint_id), None)

    def _remove_endpoint_entities(
        self, node: MatterNode, endpoint: MatterEndpoint
    ) -> None:
        """Remove the entities of an endpoint and of its composed parts.

        The entities can be on the node device, a child device or a bridged
        device, so they are found by their unique ID, which starts with the id
        of the endpoint's device and the endpoint id.
        """
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        endpoint_ids = _get_endpoint_and_part_ids(node, endpoint.endpoint_id)
        unique_id_prefixes = _get_unique_id_prefixes(server_info, node, endpoint_ids)
        entity_registry = er.async_get(self.hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        ):
            if entity_entry.unique_id.startswith(unique_id_prefixes):
                entity_registry.async_remove(entity_entry.entity_id)
        self._forget_endpoint_entities(node.node_id, endpoint_ids)

    def _reload_if_child_device_owners_changed(self, node: MatterNode) -> None:
        """Reload when created entities belong on another device by now.

        E.g. a new endpoint can make an existing sibling split into a child device,
        which its already created entities only pick up when they are recreated.
        The same goes for a child device whose name changed, which is otherwise
        only renamed when one of its entities is added.
        """
        if node.is_bridge_device:
            return
        for endpoint in node.endpoints.values():
            key = (node.node_id, endpoint.endpoint_id)
            if key not in self._child_device_owners:
                continue
            if self._child_device_owners[key] != _get_child_device_placement(endpoint):
                self._schedule_reload()
                return

    def _schedule_reload(self) -> None:
        """Schedule a reload of the config entry, once per adapter."""
        if self._reload_scheduled:
            return
        self._reload_scheduled = True
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    def _create_device_registry(
        self,
        endpoint: MatterEndpoint,
    ) -> None:
        """Create a device registry entry for a MatterNode."""
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)

        # All endpoints of a composed device share a single device registry entry,
        # so derive that entry from the compose parent for every one of them.
        endpoint = get_device_endpoint(endpoint)

        # a Bridged Node without BridgedDeviceBasicInformation gets a device without its info
        basic_info = endpoint.device_info or clusters.BridgedDeviceBasicInformation()
        node_info = endpoint.node.device_info
        # use (first) DeviceType of the endpoint as fallback product name
        device_type = next(
            (
                x
                for x in endpoint.device_types
                if x.device_type != BridgedNode.device_type
            ),
            None,
        )
        name = (
            get_clean_name(basic_info.nodeLabel)
            or get_clean_name(basic_info.productLabel)
            or get_clean_name(basic_info.productName)
            or (device_type.__name__ if device_type else None)
        )

        device_registry = dr.async_get(self.hass)

        # handle bridged devices
        via_device_id: str | Undefined = Undefined
        if endpoint.is_bridged_device and endpoint.node.endpoints[0] != endpoint:
            bridge_device_id = get_device_id(
                server_info,
                endpoint.node.endpoints[0],
            )
            via_device_id = dr.async_get_device_id_by_identifier(
                self.hass,
                (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{bridge_device_id}"),
                config_entry_id=self.config_entry.entry_id,
            )

        node_device_id = get_device_id(
            server_info,
            endpoint,
        )
        node_device_identifier = (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")
        identifiers = {node_device_identifier}
        serial_number: str | None = None
        # if available, we also add the serial number as identifier
        if (
            (basic_info_serial_number := basic_info.serialNumber)
            and "test" not in basic_info_serial_number.lower()
            # some bridges report their own serial number for the devices they bridge,
            # which would make the identifier resolve to the bridge's device
            and not (
                isinstance(basic_info, clusters.BridgedDeviceBasicInformation)
                and node_info is not None
                and basic_info_serial_number == node_info.serialNumber
            )
        ):
            # prefix identifier with 'serial_' to be able to filter it
            identifiers.add((DOMAIN, f"{ID_TYPE_SERIAL}_{basic_info_serial_number}"))
            serial_number = basic_info_serial_number

        # the bridge's device entry keeps every identifier that was ever merged onto
        # it, so a bridged device can still resolve to it through one left behind
        if (
            via_device_id is not Undefined
            and (via_device := device_registry.async_get(via_device_id))
            and (stale_identifiers := via_device.identifiers & identifiers)
        ):
            device_registry.async_update_device(
                via_device.id,
                new_identifiers=via_device.identifiers - stale_identifiers,
            )

        # Model name is the human readable name of the model/product name
        model_name = (
            # productLabel is optional but preferred (e.g. Hue Bloom)
            get_clean_name(basic_info.productLabel)
            # alternative is the productName (e.g. LCT001)
            or get_clean_name(basic_info.productName)
            # if no product name, use the device type name
            or (device_type.__name__ if device_type else None)
        )
        # Model ID is the non-human readable product ID
        # we prefer the matter product ID so we can look it up in Matter DCL
        if isinstance(basic_info, clusters.BridgedDeviceBasicInformation):
            # On bridged devices, the productID is not available
            model_id = None
        else:
            model_id = str(product_id) if (product_id := basic_info.productID) else None

        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            name=name,
            identifiers=identifiers,
            hw_version=basic_info.hardwareVersionString,
            sw_version=basic_info.softwareVersionString,
            manufacturer=basic_info.vendorName
            or (node_info.vendorName if node_info is not None else None),
            model=model_name,
            model_id=model_id,
            serial_number=serial_number,
            suggested_area=get_suggested_area(endpoint),
            via_device_id=via_device_id,
        )

    def _setup_endpoint(self, endpoint: MatterEndpoint) -> None:
        """Set up a MatterEndpoint as HA Device."""
        if self._reload_scheduled:
            # The reload sets up the entities again.
            return
        # pre-create device registry entry
        self._create_device_registry(endpoint)
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        device_id = get_device_id(server_info, endpoint)
        legacy_device_id = get_legacy_device_id(server_info, endpoint)
        discovered = self.discovered_entities.setdefault(
            (endpoint.node.node_id, endpoint.endpoint_id), set()
        )
        child_device_placement = _get_child_device_placement(endpoint)
        # run platform discovery from device type instances
        for entity_info in async_discover_entities(
            endpoint, server_info.schema_version
        ):
            discovery_key = get_discovery_key(endpoint, entity_info)
            if discovery_key in discovered:
                continue
            if legacy_device_id != device_id:
                self._migrate_legacy_unique_id(
                    endpoint, entity_info, legacy_device_id, device_id
                )
            LOGGER.debug(
                "Creating %s entity for %s",
                entity_info.platform,
                entity_info.primary_attribute,
            )
            discovered.add(discovery_key)
            self._child_device_owners.setdefault(
                (endpoint.node.node_id, endpoint.endpoint_id), child_device_placement
            )
            new_entity = entity_info.entity_class(
                self.matter_client, endpoint, entity_info
            )
            self.platform_handlers[entity_info.platform]([new_entity])

    def _migrate_legacy_unique_id(
        self,
        endpoint: MatterEndpoint,
        entity_info: MatterEntityInfo,
        legacy_device_id: str,
        device_id: str,
    ) -> None:
        """Rename an entity registry entry still using the pre-1.5.0 unique_id.

        matter-python-client 1.5.0 changed `get_compose_parent()` to resolve to the
        top of a composition instead of the closest parent, which changes the
        unique_id of a part nested below another part. Rename the entity registry
        entry so its entity_id (and any automation referencing it) survives the
        client upgrade, instead of orphaning it and creating a new entity.
        """
        legacy_unique_id = get_entity_unique_id(legacy_device_id, endpoint, entity_info)
        entity_registry = er.async_get(self.hass)
        if entity_id := entity_registry.async_get_entity_id(
            entity_info.platform, DOMAIN, legacy_unique_id
        ):
            entity_registry.async_update_entity(
                entity_id,
                new_unique_id=get_entity_unique_id(device_id, endpoint, entity_info),
            )
