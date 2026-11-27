"""Move commissioned Thread devices onto another Thread network.

A Thread device keeps its network in the Network Commissioning cluster, so it
moves without leaving the fabric: stage the new dataset under an armed
fail-safe, connect, and complete. A device that cannot reach the new network
returns to its previous one when the fail-safe expires.
"""

import asyncio
from base64 import b64decode
from collections.abc import AsyncIterator, Awaitable, Callable
import contextlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.exceptions import MatterClientException
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import create_attribute_path
from python_otbr_api import tlv_parser

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, FLEET_MIGRATION, LOGGER, MIGRATED
from .thread_border_router import (
    async_reconfiguring,
    check_commissioning_response,
    is_reconfiguring,
    network_change_pending,
)

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

# Covers staging, the attach, the controller finding the device again and
# CommissioningComplete, each of which a sleepy device can take minutes over:
# the longest fail-safe the spec allows.
FAIL_SAFE_EXPIRY = 900  # seconds
# Counted from arming, and ends before the fail-safe does, so a reported
# failure is a device that returns to its previous network. Both shrink in
# proportion to fit a device's maximum cumulative fail-safe time.
COMPLETE_DEADLINE = 840  # seconds
COMPLETE_RETRY_DELAY = 15  # seconds

# Result of a move the device needed none of
ALREADY_ON_NETWORK = "already_on_network"

_THREAD_FEATURE = clusters.NetworkCommissioning.Bitmaps.Feature.kThreadNetworkInterface
_STATUS = clusters.NetworkCommissioning.Enums.NetworkCommissioningStatusEnum
_NO_FAIL_SAFE = clusters.GeneralCommissioning.Enums.CommissioningErrorEnum.kNoFailSafe
_ROLE = clusters.ThreadNetworkDiagnostics.Enums.RoutingRoleEnum

# End devices depend on routers of the network they leave, so they go first;
# the leader goes last.
_MIGRATION_ORDER: dict[int, int] = {
    _ROLE.kSleepyEndDevice: 0,
    _ROLE.kEndDevice: 0,
    _ROLE.kReed: 1,
    _ROLE.kRouter: 2,
    _ROLE.kLeader: 3,
}

_EXTENDED_PAN_ID_PATH = create_attribute_path(
    0,
    clusters.ThreadNetworkDiagnostics.id,
    clusters.ThreadNetworkDiagnostics.Attributes.ExtendedPanId.attribute_id,
)
_NETWORKS_PATH = create_attribute_path(
    0,
    clusters.NetworkCommissioning.id,
    clusters.NetworkCommissioning.Attributes.Networks.attribute_id,
)


def get_thread_network_endpoint(node: MatterNode) -> MatterEndpoint | None:
    """Return the root endpoint if it carries the device's Thread network."""
    endpoint = node.endpoints.get(0)
    if endpoint is None or not endpoint.has_cluster(clusters.NetworkCommissioning):
        return None
    feature_map = endpoint.get_attribute_value(
        None, clusters.NetworkCommissioning.Attributes.FeatureMap
    )
    if not isinstance(feature_map, int) or not feature_map & _THREAD_FEATURE:
        return None
    return endpoint


def _network_id(value: Any) -> bytes | None:
    """Return an extended PAN ID as a network ID; None when absent, null or out of range."""
    if not isinstance(value, int) or not 0 <= value < 1 << 64:
        return None
    return value.to_bytes(8, "big")


def _networks(value: Any) -> list[tuple[bytes, bool]]:
    """Return a Networks attribute as (network ID, connected) pairs.

    Cached, it holds NetworkInfoStruct objects; read, the raw form, with the
    network ID base64 encoded.
    """
    pairs: list[tuple[bytes, bool]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            raw, connected = item.get("0"), item.get("1")
            try:
                network = (
                    b64decode(raw, validate=True) if isinstance(raw, str) else None
                )
            except ValueError:
                network = None
        else:
            network = getattr(item, "networkID", None)
            connected = getattr(item, "connected", None)
        if isinstance(network, bytes) and len(network) == 8:
            pairs.append((network, connected is True))
    return pairs


def _network_of(diagnostics: Any, networks: Any, *, attached: bool) -> bytes | None:
    """Return the network a device is on, by its diagnostics or its networks.

    The diagnostics name the network a device holds while it is detached
    too: with `attached`, networks read that do not show it connected
    outweigh them, none at all included. Without `attached`, a device that holds a single network counts as
    on it; that is the entry to remove before staging another.
    """
    pairs = _networks(networks)
    if (network := _network_id(diagnostics)) is not None:
        if attached and isinstance(networks, list) and (network, True) not in pairs:
            return None
        return network
    if connected := [network for network, is_connected in pairs if is_connected]:
        return connected[0]
    if not attached and len(pairs) == 1:
        return pairs[0][0]
    return None


def _fail_safe_window(node: MatterNode) -> tuple[int, float]:
    """Return the fail-safe to arm and the time to complete within, from arming.

    A device ends a fail-safe at its maximum cumulative fail-safe time,
    whatever was asked for.
    """
    info = node.get_attribute_value(
        0, None, clusters.GeneralCommissioning.Attributes.BasicCommissioningInfo
    )
    limit = getattr(info, "maxCumulativeFailsafeSeconds", None)
    expiry = FAIL_SAFE_EXPIRY
    if isinstance(limit, int) and 0 < limit < expiry:
        expiry = limit
    return expiry, COMPLETE_DEADLINE * expiry / FAIL_SAFE_EXPIRY


def _cached_networks(endpoint: MatterEndpoint) -> tuple[Any, Any]:
    """Return the network attributes the device last reported."""
    return (
        endpoint.get_attribute_value(
            None, clusters.ThreadNetworkDiagnostics.Attributes.ExtendedPanId
        ),
        endpoint.get_attribute_value(
            None, clusters.NetworkCommissioning.Attributes.Networks
        ),
    )


def get_migration_order(endpoint: MatterEndpoint) -> int:
    """Return when to move the device among others: end devices first.

    A device whose role is unknown goes between the end devices and the
    routers: before the routers it may depend on, after the end devices that
    may depend on it.
    """
    role = endpoint.get_attribute_value(
        None, clusters.ThreadNetworkDiagnostics.Attributes.RoutingRole
    )
    return _MIGRATION_ORDER.get(role, 1)


def network_id_from_dataset(dataset: bytes) -> bytes:
    """Return the network ID, the extended PAN ID, of a dataset the Thread store holds."""
    entries = tlv_parser.parse_tlv(dataset.hex())
    return bytes(entries[tlv_parser.MeshcopTLVType.EXTPANID].data)


def _migration_failed(error: str) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="thread_migration_failed",
        translation_placeholders={"error": error},
    )


def _check_network_response(response: Any, command: str, *accepted: int) -> None:
    """Raise when a Network Commissioning command reports failure.

    The status is in the response, so a failed step reads as success
    otherwise.
    """
    status = response.get("networkingStatus") if isinstance(response, dict) else None
    if status is not None and status not in (_STATUS.kSuccess, *accepted):
        detail = f"{command} returned status {status} {response.get('debugText') or ''}"
        raise _migration_failed(detail.strip())


async def _async_read_networks(
    matter_client: MatterClient, endpoint: MatterEndpoint
) -> tuple[Any, Any] | None:
    """Read the network attributes from the device; None when it does not answer."""
    paths = [_NETWORKS_PATH]
    if endpoint.has_cluster(clusters.ThreadNetworkDiagnostics):
        paths.insert(0, _EXTENDED_PAN_ID_PATH)
    try:
        values = await matter_client.read_attribute(endpoint.node.node_id, paths)
    except MatterError, MatterClientException:
        return None
    return values.get(_EXTENDED_PAN_ID_PATH), values.get(_NETWORKS_PATH)


def _check_no_network_change(hass: HomeAssistant) -> None:
    """Refuse a move while a pending dataset may still move a network."""
    if network_change_pending(hass):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_network_change_pending"
        )


@asynccontextmanager
async def async_fleet_migration(hass: HomeAssistant) -> AsyncIterator[None]:
    """Run one fleet migration at a time, with no single move alongside.

    A second run, or a single move, could take a router ahead of the end
    devices the first run has not moved yet.
    """
    if hass.data.get(FLEET_MIGRATION):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_migration_running"
        )
    if is_reconfiguring(hass):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="node_reconfiguring"
        )
    _check_no_network_change(hass)
    hass.data[FLEET_MIGRATION] = True
    try:
        yield
    finally:
        hass.data.pop(FLEET_MIGRATION, None)


async def async_migrate_device(
    hass: HomeAssistant,
    matter_client: MatterClient,
    endpoint: MatterEndpoint,
    dataset: bytes,
    *,
    in_fleet: bool = False,
) -> str:
    """Move a Thread device onto the network of the dataset.

    Returns MIGRATED or ALREADY_ON_NETWORK. A device that fails after it was
    told to connect returns to its previous network when the fail-safe
    expires; it stays held until then.
    """
    if not in_fleet and hass.data.get(FLEET_MIGRATION):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_migration_running"
        )
    _check_no_network_change(hass)
    async with async_reconfiguring(hass, endpoint.node.node_id) as keep_until:
        return await _async_migrate(matter_client, endpoint, dataset, keep_until)


def _check_time_left(deadline: float) -> None:
    """Raise when a switch started now could no longer be completed."""
    if asyncio.get_running_loop().time() >= deadline:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="thread_migration_not_switched",
        )


async def _within[_T](awaitable: Awaitable[_T], remaining: float) -> _T | None:
    """Await within the time remaining; None when it runs out."""
    try:
        async with asyncio.timeout(remaining):
            return await awaitable
    except TimeoutError:
        return None


async def _async_migrate(
    matter_client: MatterClient,
    endpoint: MatterEndpoint,
    dataset: bytes,
    keep_until: Callable[[float], None],
) -> str:
    node = endpoint.node
    target = network_id_from_dataset(dataset)
    # Thread diagnostics are reported lazily, so the cache can name a network
    # the device has left, or one a rolled back move left behind: only the
    # device can tell that it is on the target, the cache only which entry
    # to remove when it does not answer.
    if (live := await _async_read_networks(matter_client, endpoint)) is not None:
        if _network_of(*live, attached=True) == target:
            return ALREADY_ON_NETWORK
        previous = _network_of(*live, attached=False)
    elif (previous := _network_of(*_cached_networks(endpoint), attached=False)) in (
        None,
        target,
    ):
        # The cache may have outlived a rolled back move: the device's single
        # network entry may hold another network, which would refuse the new
        # one. Only the device can tell.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="thread_network_unreadable"
        )

    commissioning = clusters.GeneralCommissioning.Commands
    network = clusters.NetworkCommissioning.Commands
    loop = asyncio.get_running_loop()

    async def send(command: Any) -> Any:
        try:
            return await matter_client.send_device_command(
                node_id=node.node_id, endpoint_id=0, command=command
            )
        except (MatterError, MatterClientException) as err:
            raise _migration_failed(str(err) or err.__class__.__name__) from err

    async def disarm() -> None:
        # Released once the device accepts the rollback.
        with contextlib.suppress(HomeAssistantError):
            response = await send(commissioning.ArmFailSafe(expiryLengthSeconds=0))
            check_commissioning_response(
                response, "ArmFailSafe", "thread_migration_failed"
            )
            keep_until(0)

    # Completing is given up before the fail-safe can have expired, counted
    # from before the arm. The hold runs from when the arm attempt ends: one
    # whose answer got lost or came late may have taken until then.
    expiry, complete_within = _fail_safe_window(node)
    deadline = loop.time() + complete_within
    try:
        response = await send(
            commissioning.ArmFailSafe(expiryLengthSeconds=expiry, breadcrumb=1)
        )
    finally:
        keep_until(loop.time() + expiry)
    try:
        check_commissioning_response(response, "ArmFailSafe", "thread_migration_failed")
    except HomeAssistantError:
        # Refused: nothing is armed.
        keep_until(0)
        raise
    try:
        if previous not in (None, target):
            # A dataset for another network is refused while the old entry
            # exists. An entry already gone is a rerun.
            response = await send(
                network.RemoveNetwork(networkID=previous, breadcrumb=2)
            )
            _check_network_response(
                response, "RemoveNetwork", _STATUS.kNetworkIDNotFound
            )
        response = await send(
            network.AddOrUpdateThreadNetwork(operationalDataset=dataset, breadcrumb=3)
        )
        _check_network_response(response, "AddOrUpdateThreadNetwork")
        _check_time_left(deadline)
        try:
            response = await send(
                network.ConnectNetwork(networkID=target, breadcrumb=4)
            )
        except HomeAssistantError:
            # The device detaches as it acts on this, so the answer may be lost.
            LOGGER.debug("No answer to ConnectNetwork from node %s", node.node_id)
        else:
            _check_network_response(response, "ConnectNetwork")
    except HomeAssistantError:
        # The device has not left its network: revert it now.
        await disarm()
        raise

    # Completed only once the device answers from the new network, and only
    # within the deadline: a completion the fail-safe may have outrun could
    # read as committed. A device that cannot be reached is not disarmed: the
    # fail-safe takes it back.
    unanswered = False
    current: bytes | None = None
    while (remaining := deadline - loop.time()) > 0:
        live = await _within(_async_read_networks(matter_client, endpoint), remaining)
        current = _network_of(*live, attached=True) if live is not None else None
        if current == target and (remaining := deadline - loop.time()) > 0:
            try:
                async with asyncio.timeout(remaining):
                    response = await matter_client.send_device_command(
                        node_id=node.node_id,
                        endpoint_id=0,
                        command=commissioning.CommissioningComplete(),
                    )
            except MatterError, MatterClientException, TimeoutError:
                # It may have been committed with only the answer lost.
                unanswered = True
            else:
                if not (
                    unanswered
                    and isinstance(response, dict)
                    and response.get("errorCode") == _NO_FAIL_SAFE
                ):
                    check_commissioning_response(
                        response, "CommissioningComplete", "thread_migration_failed"
                    )
                # Committed, now or by an earlier completion whose answer got lost
                keep_until(0)
                return MIGRATED
        if (remaining := deadline - loop.time()) <= 0:
            break
        # Makes the controller look up the device's new address.
        with contextlib.suppress(MatterError, MatterClientException):
            await _within(matter_client.ping_node(node.node_id), remaining)
        await asyncio.sleep(max(0.0, min(COMPLETE_RETRY_DELAY, deadline - loop.time())))

    if current not in (None, target):
        # Still on another network: the switch never happened.
        await disarm()
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="thread_migration_not_switched",
        )
    if unanswered:
        # A completion may have been committed: no rollback to promise.
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="thread_migration_unconfirmed",
        )
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="thread_migration_unreachable",
    )
