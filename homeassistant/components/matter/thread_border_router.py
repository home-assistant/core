"""Thread datasets of Matter border routers.

A router with the Thread Border Router Management cluster hands its active
dataset to a fabric member with the Manage privilege. The user imports it with
the router's button; the stored dataset of a network Home Assistant knows is
kept in step with its border routers.
"""

from base64 import b64decode
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.models import device_types
from matter_server.common.errors import MatterError, NodeNotExists
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.thread import (
    DOMAIN as THREAD_DOMAIN,
    async_add_dataset,
    async_get_store,
    async_update_dataset,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

    from homeassistant.components.thread import DatasetStore

    from .helpers import MatterConfigEntry

THREAD_DATASET_RETRY_DELAY = 30  # seconds
THREAD_DATASET_READ_ATTEMPTS = 3

# Both device types carry the TBRM cluster.
BORDER_ROUTER_DEVICE_TYPES = (
    device_types.NetworkInfrastructureManager,
    device_types.ThreadBorderRouter,
)


def get_dataset_attribute_paths(endpoint: MatterEndpoint) -> list[str]:
    """Return the paths of the attributes whose change calls for a new read."""
    return [
        create_attribute_path(
            endpoint.endpoint_id,
            clusters.ThreadBorderRouterManagement.id,
            clusters.ThreadBorderRouterManagement.Attributes.ActiveDatasetTimestamp.attribute_id,
        ),
        create_attribute_path(
            endpoint.endpoint_id,
            clusters.ThreadNetworkDiagnostics.id,
            clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress.attribute_id,
        ),
        create_attribute_path(
            endpoint.endpoint_id,
            clusters.ThreadNetworkDiagnostics.id,
            clusters.ThreadNetworkDiagnostics.Attributes.ExtendedPanId.attribute_id,
        ),
    ]


def get_border_router_endpoints(node: MatterNode) -> list[MatterEndpoint]:
    """Return the endpoints of a node that expose a Thread border router."""
    return [
        endpoint
        for endpoint in node.endpoints.values()
        if endpoint.has_cluster(clusters.ThreadBorderRouterManagement)
        and any(
            device_type in BORDER_ROUTER_DEVICE_TYPES
            for device_type in endpoint.device_types
        )
    ]


def get_extended_address(endpoint: MatterEndpoint) -> Any:
    """Return the ExtAddress attribute: NullValue without a Thread stack, None when absent."""
    return endpoint.get_attribute_value(
        None, clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress
    )


def get_active_dataset_timestamp(endpoint: MatterEndpoint) -> int | None:
    """Return the active dataset timestamp, which changes when the dataset does."""
    timestamp: int | None = endpoint.get_attribute_value(
        None, clusters.ThreadBorderRouterManagement.Attributes.ActiveDatasetTimestamp
    )
    return timestamp


def get_extended_pan_id(endpoint: MatterEndpoint) -> str | None:
    """Return the router's extended PAN ID as hex, None when it reports none."""
    value = endpoint.get_attribute_value(
        None, clusters.ThreadNetworkDiagnostics.Attributes.ExtendedPanId
    )
    if value in (None, NullValue):
        return None
    return int(value).to_bytes(8, "big").hex()


def _dataset_from_response(response: Any) -> bytes:
    """Return the dataset of a DatasetResponse; raise ValueError without one."""
    raw = response.get("dataset") if isinstance(response, dict) else None
    if isinstance(raw, str):
        return b64decode(raw, validate=True)
    raise ValueError("response carries no dataset payload")


async def async_read_dataset(
    matter_client: MatterClient, endpoint: MatterEndpoint
) -> bytes:
    """Read the active dataset from a border router; empty when it has none."""
    response: Any = await matter_client.send_device_command(
        node_id=endpoint.node.node_id,
        endpoint_id=endpoint.endpoint_id,
        command=clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest(),
    )
    return _dataset_from_response(response)


async def async_ensure_thread_setup(hass: HomeAssistant) -> None:
    """Set up the Thread integration unless it has a config entry already."""
    if hass.config_entries.async_entries(THREAD_DOMAIN):
        return
    await hass.config_entries.flow.async_init(
        THREAD_DOMAIN, context={"source": SOURCE_IMPORT}
    )


async def async_store_dataset(
    hass: HomeAssistant,
    endpoint: MatterEndpoint,
    dataset: bytes,
    *,
    update_only: bool = False,
) -> None:
    """Add a border router's dataset to the store."""
    if not dataset:
        LOGGER.debug(
            "Border router on node %s endpoint %s has no active dataset",
            endpoint.node.node_id,
            endpoint.endpoint_id,
        )
        return

    border_agent_id: bytes | None = endpoint.get_attribute_value(
        None, clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID
    )
    ext_address: int | None = get_extended_address(endpoint)

    # The store takes both or neither; NullValue (no Thread stack) is truthy.
    preferred: dict[str, str] = {}
    if border_agent_id and ext_address not in (None, NullValue):
        preferred = {
            "preferred_border_agent_id": border_agent_id.hex(),
            "preferred_extended_address": ext_address.to_bytes(8, "big").hex(),
        }

    # Stored first: setting Thread up can take a while, and the caller's checks
    # hold only until the store write.
    add = async_update_dataset if update_only else async_add_dataset
    await add(hass, DOMAIN, dataset.hex(), **preferred)
    await async_ensure_thread_setup(hass)

    LOGGER.debug(
        "Imported Thread dataset from node %s endpoint %s",
        endpoint.node.node_id,
        endpoint.endpoint_id,
    )


@dataclass
class _Router:
    """Bookkeeping for one border router endpoint."""

    unsubscribe: Callable[[], None]
    # (active dataset timestamp, extended address, extended PAN ID) last read from
    state: tuple[Any, Any, str | None] | None = None
    # The id of the stored dataset the last completed read kept in step
    stored: str | None = None
    reading: bool = False
    read_again: bool = False
    failures: int = 0
    cancel_retry: Callable[[], None] | None = None

    def cancel_pending_retry(self) -> None:
        """Drop a retry that has not fired yet."""
        if self.cancel_retry:
            self.cancel_retry()
            self.cancel_retry = None

    def release(self) -> None:
        """Stop listening and drop a pending retry."""
        self.unsubscribe()
        self.cancel_pending_retry()


class ThreadDatasetImporter:
    """Import border routers' datasets on request and follow the networks the store holds.

    A router is read when the user presses its button, and again whenever it
    reports a new active dataset timestamp, extended address or extended PAN ID
    while the store holds a dataset for its network; such a read only updates
    the store, it adds no network.
    """

    def __init__(
        self, hass: HomeAssistant, matter_client: MatterClient, entry: MatterConfigEntry
    ) -> None:
        """Initialize the importer."""
        self.hass = hass
        self.matter_client = matter_client
        self.entry = entry
        self._routers: dict[tuple[int, int], _Router] = {}
        self._store: DatasetStore | None = None

    async def _async_store(self) -> DatasetStore:
        """Return the dataset store, kept for the lookups the event handlers make."""
        self._store = await async_get_store(self.hass)
        return self._store

    @callback
    def async_setup(self) -> None:
        """Track the border routers of all nodes, now and as they come and go."""
        subscribe = self.matter_client.subscribe_events
        for event, handler in (
            (EventType.NODE_ADDED, self._node_event),
            (EventType.NODE_UPDATED, self._node_event),
            (EventType.ENDPOINT_ADDED, self._endpoint_added),
            (EventType.ENDPOINT_REMOVED, self._endpoint_removed),
            (EventType.NODE_REMOVED, self._node_removed),
        ):
            self.entry.async_on_unload(subscribe(callback=handler, event_filter=event))
        self.entry.async_on_unload(self._release_all)
        for node in self.matter_client.get_nodes():
            self._schedule(node)

    async def async_import(self, endpoint: MatterEndpoint) -> None:
        """Import a border router's dataset now."""
        key = (endpoint.node.node_id, endpoint.endpoint_id)
        state = _state_of(endpoint)
        try:
            dataset = await async_read_dataset(self.matter_client, endpoint)
        except MatterError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="thread_dataset_read_failed",
                translation_placeholders={"error": str(err) or err.__class__.__name__},
            ) from err
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="thread_dataset_unusable"
            ) from err
        if not dataset:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="thread_network_missing"
            )
        await async_store_dataset(self.hass, endpoint, dataset)
        if router := self._routers.get(key):
            # The read started from `state`; a change since then is read now.
            router.state = state
            router.stored = _stored_id(
                await self._async_store(), get_extended_pan_id(endpoint)
            )
            router.failures = 0
            router.cancel_pending_retry()
            self._schedule(endpoint.node)

    @callback
    def _node_event(self, event: EventType, node: MatterNode) -> None:
        self._schedule(node)

    @callback
    def _endpoint_added(self, event: EventType, data: dict[str, int]) -> None:
        try:
            node = self.matter_client.get_node(data["node_id"])
        except NodeNotExists:
            return
        self._schedule(node)

    @callback
    def _endpoint_removed(self, event: EventType, data: dict[str, int]) -> None:
        if router := self._routers.pop((data["node_id"], data["endpoint_id"]), None):
            router.release()

    @callback
    def _node_removed(self, event: EventType, node_id: int) -> None:
        for key in [key for key in self._routers if key[0] == node_id]:
            self._routers.pop(key).release()

    @callback
    def _release_all(self) -> None:
        while self._routers:
            self._routers.popitem()[1].release()

    @callback
    def _schedule(
        self, node: MatterNode, retrying: tuple[int, int] | None = None
    ) -> None:
        """Read the border routers of a node whose dataset may have changed.

        `retrying` names the endpoint whose retry timer fired: it alone is read,
        keeping its count of attempts.
        """
        if not node.available:
            return
        for endpoint in get_border_router_endpoints(node):
            key = (node.node_id, endpoint.endpoint_id)
            if retrying not in (None, key):
                continue
            if (router := self._routers.get(key)) is None:
                router = self._routers[key] = _Router(
                    self._subscribe(node.node_id, endpoint)
                )
            state = _state_of(endpoint)
            # The store's dataset for the network changed hands: followed anew.
            # A read in flight records it, and checks it again, when it completes.
            if (
                not router.reading
                and self._store is not None
                and router.stored != _stored_id(self._store, state[2])
            ):
                router.state = None
            if router.state == state:
                continue
            router.state = state
            if router.reading:
                # The read in flight may answer with the dataset just replaced.
                router.read_again = True
                continue
            router.cancel_pending_retry()
            if retrying is None:
                router.failures = 0
            router.reading = True
            router.read_again = False
            self.entry.async_create_background_task(
                self.hass,
                self._read(key, router, endpoint),
                name=f"matter_thread_dataset_{key[0]}_{key[1]}",
            )

    async def _read(
        self, key: tuple[int, int], router: _Router, endpoint: MatterEndpoint
    ) -> None:
        """Read a border router's dataset into the store if its network is known."""
        retry = False
        try:
            # Loaded before the read: adding to a loaded store does not wait.
            store = await self._async_store()
            xpan = get_extended_pan_id(endpoint)
            if _stored_id(store, xpan) is None:
                # Not followed; the next event looks the network up again.
                router.state = None
                router.stored = None
            else:
                dataset = await async_read_dataset(self.matter_client, endpoint)
                # Dropped when the router went away or a change overtook the read;
                # a network deleted meanwhile is looked up again at the next event.
                if self._routers.get(key) is router and not router.read_again:
                    router.stored = _stored_id(store, xpan)
                    if router.stored is None:
                        router.state = None
                    else:
                        await async_store_dataset(
                            self.hass, endpoint, dataset, update_only=True
                        )
        except MatterError as err:
            router.state = None
            router.failures += 1
            retry = router.failures < THREAD_DATASET_READ_ATTEMPTS
            if retry:
                LOGGER.debug(
                    "Reading the Thread dataset of node %s endpoint %s failed,"
                    " trying again: %s",
                    *key,
                    err,
                )
            else:
                router.failures = 0
                LOGGER.warning(
                    "Could not read the Thread dataset of node %s endpoint %s: %s",
                    *key,
                    err,
                )
        except (HomeAssistantError, ValueError) as err:
            # An unusable response or dataset; the next change reads again.
            router.state = None
            router.failures = 0
            LOGGER.warning(
                "Could not import the Thread dataset of node %s endpoint %s: %s",
                *key,
                err,
            )
        else:
            router.failures = 0
        router.reading = False
        if self._routers.get(key) is not router:
            return
        if router.read_again:
            router.read_again = False
            router.state = None
            try:
                node = self.matter_client.get_node(key[0])
            except NodeNotExists:
                return
            self._schedule(node)
        elif retry:

            @callback
            def _retry(_now: datetime) -> None:
                router.cancel_retry = None
                try:
                    node = self.matter_client.get_node(key[0])
                except NodeNotExists:
                    return
                self._schedule(node, retrying=key)

            router.cancel_retry = async_call_later(
                self.hass, THREAD_DATASET_RETRY_DELAY, _retry
            )

    def _subscribe(self, node_id: int, endpoint: MatterEndpoint) -> Callable[[], None]:
        """Schedule a read when the router's dataset timestamp or address changes."""

        def updated_callback(event: EventType, data: Any) -> None:
            try:
                node = self.matter_client.get_node(node_id)
            except NodeNotExists:
                return
            self._schedule(node)

        unsubscribes = [
            self.matter_client.subscribe_events(
                callback=updated_callback,
                event_filter=EventType.ATTRIBUTE_UPDATED,
                node_filter=node_id,
                attr_path_filter=path,
            )
            for path in get_dataset_attribute_paths(endpoint)
        ]

        def unsubscribe() -> None:
            for unsubscribe_path in unsubscribes:
                unsubscribe_path()

        return unsubscribe


def _state_of(endpoint: MatterEndpoint) -> tuple[Any, Any, str | None]:
    """Return what a read of this router depends on."""
    return (
        get_active_dataset_timestamp(endpoint),
        get_extended_address(endpoint),
        get_extended_pan_id(endpoint),
    )


def _stored_id(store: DatasetStore, extended_pan_id: str | None) -> str | None:
    """Return the id of the store's dataset for a network, None without one."""
    return next(
        (
            entry.id
            for entry in store.datasets.values()
            if entry.extended_pan_id == extended_pan_id
        ),
        None,
    )
