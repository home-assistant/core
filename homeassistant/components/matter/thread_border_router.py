"""Import Thread operational datasets from Matter border routers.

A router that implements the Network Infrastructure Manager device type carries
the Thread Border Router Management cluster, which lets an authorised member of
the fabric read the active operational dataset over Matter. That replaces
reading the same credentials from a vendor specific API such as the OpenThread
Border Router REST interface.
"""

from base64 import b64decode
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.models import device_types
from matter_server.common.helpers.util import create_attribute_path

from homeassistant.components.thread import async_add_dataset
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

# A border router may present either device type; both carry the TBRM cluster.
BORDER_ROUTER_DEVICE_TYPES = {
    device_types.NetworkInfrastructureManager.device_type,
    device_types.ThreadBorderRouter.device_type,
}


def get_active_dataset_timestamp_path(endpoint: MatterEndpoint) -> str:
    """Return the attribute path of ActiveDatasetTimestamp on this endpoint."""
    return create_attribute_path(
        endpoint.endpoint_id,
        clusters.ThreadBorderRouterManagement.id,
        clusters.ThreadBorderRouterManagement.Attributes.ActiveDatasetTimestamp.attribute_id,
    )


def get_border_router_endpoints(node: MatterNode) -> list[MatterEndpoint]:
    """Return the endpoints of a node that expose a Thread border router."""
    return [
        endpoint
        for endpoint in node.endpoints.values()
        if endpoint.has_cluster(clusters.ThreadBorderRouterManagement)
        and any(
            device_type.device_type in BORDER_ROUTER_DEVICE_TYPES
            for device_type in endpoint.device_types
        )
    ]


def get_extended_address(endpoint: MatterEndpoint) -> Any:
    """Return the border router's Thread extended address attribute value.

    NullValue when the Thread stack is not running; None when the attribute
    is absent.
    """
    return endpoint.get_attribute_value(
        None, clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress
    )


def get_active_dataset_timestamp(endpoint: MatterEndpoint) -> int | None:
    """Return the active dataset timestamp, which changes when the dataset does."""
    timestamp: int | None = endpoint.get_attribute_value(
        None, clusters.ThreadBorderRouterManagement.Attributes.ActiveDatasetTimestamp
    )
    return timestamp


def _dataset_from_response(response: Any) -> bytes:
    """Return the dataset carried by a DatasetResponse.

    The Matter client hands back command responses as plain dicts, with octet
    strings base64 encoded rather than as bytes, so the payload cannot be read
    off the response as an attribute. Object and bytes forms are still accepted
    so this keeps working if that representation changes.

    Raises ValueError for a response that carries no readable dataset: a
    malformed reply must not be mistaken for an unprovisioned border router,
    or the import would be considered done and not tried again.
    """
    if isinstance(response, dict):
        raw = response.get("dataset")
    else:
        raw = getattr(response, "dataset", None)
    if isinstance(raw, str):
        return b64decode(raw, validate=True)
    if isinstance(raw, bytes):
        return raw
    raise ValueError("response carries no dataset payload")


async def async_import_dataset(
    hass: HomeAssistant, matter_client: MatterClient, endpoint: MatterEndpoint
) -> None:
    """Read the active dataset from a border router and add it to the store.

    The dataset is only reachable by command; the identifiers used to mark the
    preferred border agent are plain attributes on the same endpoint.
    """
    response: Any = await matter_client.send_device_command(
        node_id=endpoint.node.node_id,
        endpoint_id=endpoint.endpoint_id,
        command=clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest(),
    )
    dataset = _dataset_from_response(response)

    if not dataset:
        # A border router that has not formed or joined a network answers with
        # an empty dataset, which the dataset store would reject for lacking an
        # active timestamp.
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

    # The store refuses a preferred border agent ID that is not accompanied by an
    # extended address, so only mark a preference when both are known. A border
    # router with no Thread stack running reports ExtAddress as NullValue rather
    # than omitting it, which is not falsy and must be excluded explicitly.
    preferred: dict[str, str] = {}
    if border_agent_id and ext_address not in (None, NullValue):
        preferred = {
            "preferred_border_agent_id": border_agent_id.hex(),
            "preferred_extended_address": ext_address.to_bytes(8, "big").hex(),
        }

    await async_add_dataset(hass, DOMAIN, dataset.hex(), **preferred)

    LOGGER.debug(
        "Imported Thread dataset from node %s endpoint %s",
        endpoint.node.node_id,
        endpoint.endpoint_id,
    )
