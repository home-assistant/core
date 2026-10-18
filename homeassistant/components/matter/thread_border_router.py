"""Thread datasets of Matter border routers.

A router with the Thread Border Router Management cluster hands its active
dataset to a fabric member with the Manage privilege. The user imports it with
the router's button; the stored dataset of a network imported that way is kept
in step with its border routers.
"""

from base64 import b64decode
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.exceptions import MatterClientException
from matter_server.client.models import device_types
from matter_server.common.errors import MatterError, NodeNotExists
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.thread import (
    DOMAIN as THREAD_DOMAIN,
    DatasetAddResult,
    async_add_dataset,
    async_get_dataset_source,
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

    from .helpers import MatterConfigEntry

THREAD_DATASET_RETRY_DELAY = 30  # seconds
THREAD_DATASET_READ_ATTEMPTS = 3
# Once the quick attempts are used up
THREAD_DATASET_SLOW_RETRY_DELAY = 900  # seconds

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
    return _uint64_hex(
        endpoint.get_attribute_value(
            None, clusters.ThreadNetworkDiagnostics.Attributes.ExtendedPanId
        )
    )


def _uint64_hex(value: Any) -> str | None:
    """Return an 8-byte identifier as hex; None when absent, null or out of range."""
    if not isinstance(value, int) or not 0 <= value < 1 << 64:
        return None
    return value.to_bytes(8, "big").hex()


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
    preferred: bool = True,
) -> DatasetAddResult:
    """Add a border router's dataset to the store and set Thread up.

    With `preferred`, the router becomes the network's preferred border agent
    if the network has none yet.
    """
    pair = _border_agent(endpoint) if preferred else {}
    try:
        result = await async_add_dataset(hass, DOMAIN, dataset.hex(), **pair)
    except HomeAssistantError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_dataset_unusable"
        ) from err
    # Stored first: setting Thread up can take a while, and the caller's checks
    # hold only until the store write.
    await async_ensure_thread_setup(hass)

    LOGGER.debug(
        "Imported Thread dataset from node %s endpoint %s",
        endpoint.node.node_id,
        endpoint.endpoint_id,
    )
    return result


def _border_agent(endpoint: MatterEndpoint) -> dict[str, str]:
    """Return the router's border agent ID and extended address, or neither."""
    border_agent_id: bytes | None = endpoint.get_attribute_value(
        None, clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID
    )
    # The store takes both or neither.
    if border_agent_id and (ext_address := _uint64_hex(get_extended_address(endpoint))):
        return {
            "preferred_border_agent_id": border_agent_id.hex(),
            "preferred_extended_address": ext_address,
        }
    return {}


@dataclass
class _Router:
    """Bookkeeping for one border router endpoint."""

    unsubscribe: Callable[[], None]
    # (active dataset timestamp, extended address, extended PAN ID) last read from
    state: tuple[Any, Any, str | None] | None = None
    # Imported with the button: followed even without an extended PAN ID
    imported: bool = False
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
    """Import border routers' datasets on request and follow the networks imported.

    A router is read when the user presses its button, and again whenever it
    reports a new active dataset timestamp, extended address or extended PAN ID
    while its network is one the store holds from such an import. A router that
    reports no extended PAN ID is followed once its own button was pressed,
    until the integration is reloaded. A follow read only updates the dataset
    of a network imported here: it adds no network and sets no preferred
    border agent. A failed read is tried again a few times, then every 15
    minutes.
    """

    def __init__(
        self, hass: HomeAssistant, matter_client: MatterClient, entry: MatterConfigEntry
    ) -> None:
        """Initialize the importer."""
        self.hass = hass
        self.matter_client = matter_client
        self.entry = entry
        self._routers: dict[tuple[int, int], _Router] = {}

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
        except (MatterError, MatterClientException) as err:
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
        # A router whose address or network changed meanwhile may have
        # answered for another network: the dataset is then stored without
        # pairing the router to it.
        moved = _state_of(endpoint)[1:] != state[1:]
        result = await async_store_dataset(
            self.hass, endpoint, dataset, preferred=not moved
        )
        if router := self._routers.get(key):
            # The read started from `state`; a change since then is read now.
            router.imported = True
            router.state = state
            router.failures = 0
            router.cancel_pending_retry()
            self._schedule(endpoint.node, only=key)
        if result is DatasetAddResult.DISCARDED:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="thread_dataset_outdated"
            )

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
        self,
        node: MatterNode,
        *,
        only: tuple[int, int] | None = None,
        retrying: bool = False,
    ) -> None:
        """Read the border routers of a node whose dataset may have changed.

        `only` limits this to one endpoint. `retrying`, for its retry timer,
        reads it although nothing changed and keeps its count of attempts.
        """
        if not node.available:
            return
        for endpoint in get_border_router_endpoints(node):
            key = (node.node_id, endpoint.endpoint_id)
            if only not in (None, key):
                continue
            if (router := self._routers.get(key)) is None:
                router = self._routers[key] = _Router(
                    self._subscribe(node.node_id, endpoint)
                )
            state = _state_of(endpoint)
            if router.state == state and not retrying:
                continue
            router.state = state
            if router.reading:
                # The read in flight may answer with the dataset just replaced.
                router.read_again = True
                continue
            router.cancel_pending_retry()
            if not retrying:
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
        """Read a border router's dataset into the store if it follows its network."""
        retry_delay: int | None = None
        try:
            if await self._async_followed(router, endpoint):
                identity = _state_of(endpoint)[1:]
                dataset = await async_read_dataset(self.matter_client, endpoint)
                # Dropped when the router went away. The store takes only an
                # update of a network imported here, whichever the answer is
                # for; a router whose address or network changed meanwhile is
                # not paired to it.
                if dataset and self._routers.get(key) is router:
                    pair = (
                        _border_agent(endpoint)
                        if _state_of(endpoint)[1:] == identity
                        else {}
                    )
                    await async_update_dataset(self.hass, DOMAIN, dataset.hex(), **pair)
            else:
                # Not followed; the next event looks the network up again.
                router.state = None
        except (MatterError, MatterClientException) as err:
            # Left to the retry timer: an unchanged update keeps its attempts.
            router.failures += 1
            if router.failures < THREAD_DATASET_READ_ATTEMPTS:
                retry_delay = THREAD_DATASET_RETRY_DELAY
            else:
                retry_delay = THREAD_DATASET_SLOW_RETRY_DELAY
            if router.failures == THREAD_DATASET_READ_ATTEMPTS:
                LOGGER.warning(
                    "Could not read the Thread dataset of node %s endpoint %s,"
                    " trying again every %s minutes: %s",
                    *key,
                    THREAD_DATASET_SLOW_RETRY_DELAY // 60,
                    err,
                )
            else:
                LOGGER.debug(
                    "Reading the Thread dataset of node %s endpoint %s failed,"
                    " trying again: %s",
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
        except Exception:  # noqa: BLE001
            # The next event reads again.
            router.state = None
            router.failures = 0
            LOGGER.exception(
                "Unexpected error reading the Thread dataset of node %s endpoint %s",
                *key,
            )
        else:
            router.failures = 0
        finally:
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
            self._schedule(node, only=key)
        elif retry_delay is not None:

            @callback
            def _retry(_now: datetime) -> None:
                router.cancel_retry = None
                try:
                    node = self.matter_client.get_node(key[0])
                except NodeNotExists:
                    return
                if not node.available:
                    # Read once the node is back.
                    router.state = None
                    return
                self._schedule(node, only=key, retrying=True)

            router.cancel_retry = async_call_later(self.hass, retry_delay, _retry)

    async def _async_followed(self, router: _Router, endpoint: MatterEndpoint) -> bool:
        """Return whether the router's network is one imported here."""
        if (extended_pan_id := get_extended_pan_id(endpoint)) is None:
            return router.imported
        return await async_get_dataset_source(self.hass, extended_pan_id) == DOMAIN

    def _subscribe(self, node_id: int, endpoint: MatterEndpoint) -> Callable[[], None]:
        """Schedule a read when the router's dataset timestamp, address or network changes."""
        key = (node_id, endpoint.endpoint_id)

        def updated_callback(event: EventType, data: Any) -> None:
            try:
                node = self.matter_client.get_node(node_id)
            except NodeNotExists:
                return
            self._schedule(node, only=key)

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
