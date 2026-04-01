"""Read binding and ACL data from Matter devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable

from homeassistant.core import callback

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterNode


# Binding cluster attribute path keys (raw dict format)
_BINDING_KEY_NODE = "1"
_BINDING_KEY_GROUP = "2"
_BINDING_KEY_ENDPOINT = "3"
_BINDING_KEY_CLUSTER = "4"
_BINDING_KEY_FABRIC_INDEX = "254"

# ACL cluster attribute path keys (raw dict format)
_ACL_KEY_PRIVILEGE = "1"
_ACL_KEY_AUTH_MODE = "2"
_ACL_KEY_SUBJECTS = "3"
_ACL_KEY_TARGETS = "4"
_ACL_KEY_FABRIC_INDEX = "254"

# ACL target keys (raw dict format)
_ACL_TARGET_KEY_CLUSTER = "0"
_ACL_TARGET_KEY_ENDPOINT = "1"
_ACL_TARGET_KEY_DEVICE_TYPE = "2"

# Cluster/attribute IDs
_BINDING_CLUSTER_ID = 30
_BINDING_ATTRIBUTE_ID = 0
_ACL_CLUSTER_ID = 31
_ACL_ATTRIBUTE_ID = 0


@dataclass(frozen=True)
class BindingEntry:
    """Parsed binding table entry from a Matter device."""

    node_id: int | None
    group_id: int | None
    endpoint_id: int | None
    cluster_id: int | None
    fabric_index: int


@dataclass(frozen=True)
class ACLTarget:
    """Target constraint in an ACL entry."""

    cluster_id: int | None
    endpoint_id: int | None
    device_type_id: int | None


@dataclass(frozen=True)
class ACLEntry:
    """Parsed ACL entry from a Matter device."""

    privilege: int
    auth_mode: int
    subjects: tuple[int, ...]
    targets: tuple[ACLTarget, ...]
    fabric_index: int


def _parse_binding_entry_raw(raw: dict[str, Any]) -> BindingEntry:
    """Parse a raw binding entry dict into a BindingEntry."""
    return BindingEntry(
        node_id=raw.get(_BINDING_KEY_NODE),
        group_id=raw.get(_BINDING_KEY_GROUP),
        endpoint_id=raw.get(_BINDING_KEY_ENDPOINT),
        cluster_id=raw.get(_BINDING_KEY_CLUSTER),
        fabric_index=raw[_BINDING_KEY_FABRIC_INDEX],
    )


def _parse_acl_target_raw(raw: dict[str, Any]) -> ACLTarget:
    """Parse a raw ACL target dict into an ACLTarget."""
    return ACLTarget(
        cluster_id=raw.get(_ACL_TARGET_KEY_CLUSTER),
        endpoint_id=raw.get(_ACL_TARGET_KEY_ENDPOINT),
        device_type_id=raw.get(_ACL_TARGET_KEY_DEVICE_TYPE),
    )


def _parse_acl_entry_raw(raw: dict[str, Any]) -> ACLEntry:
    """Parse a raw ACL entry dict into an ACLEntry."""
    raw_subjects = raw.get(_ACL_KEY_SUBJECTS)
    raw_targets = raw.get(_ACL_KEY_TARGETS)
    return ACLEntry(
        privilege=raw[_ACL_KEY_PRIVILEGE],
        auth_mode=raw[_ACL_KEY_AUTH_MODE],
        subjects=tuple(raw_subjects) if raw_subjects else (),
        targets=(
            tuple(_parse_acl_target_raw(t) for t in raw_targets) if raw_targets else ()
        ),
        fabric_index=raw[_ACL_KEY_FABRIC_INDEX],
    )


def _parse_binding_entry_typed(
    entry: clusters.Binding.Structs.TargetStruct,
) -> BindingEntry:
    """Parse a typed TargetStruct into a BindingEntry."""
    return BindingEntry(
        node_id=entry.node,
        group_id=entry.group,
        endpoint_id=entry.endpoint,
        cluster_id=entry.cluster,
        fabric_index=entry.fabricIndex,
    )


def _nullable_to_none(value: Any) -> Any:
    """Convert Matter Nullable to None."""
    if isinstance(value, Nullable):
        return None
    return value


def _parse_acl_target_typed(
    target: clusters.AccessControl.Structs.AccessControlTargetStruct,
) -> ACLTarget:
    """Parse a typed AccessControlTargetStruct into an ACLTarget."""
    return ACLTarget(
        cluster_id=_nullable_to_none(target.cluster),
        endpoint_id=_nullable_to_none(target.endpoint),
        device_type_id=_nullable_to_none(target.deviceType),
    )


def _parse_acl_entry_typed(
    entry: clusters.AccessControl.Structs.AccessControlEntryStruct,
) -> ACLEntry:
    """Parse a typed AccessControlEntryStruct into an ACLEntry."""
    subjects = entry.subjects
    targets = entry.targets
    return ACLEntry(
        privilege=int(entry.privilege),
        auth_mode=int(entry.authMode),
        subjects=(
            tuple(int(s) for s in subjects)
            if not isinstance(subjects, Nullable)
            else ()
        ),
        targets=(
            tuple(_parse_acl_target_typed(t) for t in targets)
            if not isinstance(targets, Nullable)
            else ()
        ),
        fabric_index=int(entry.fabricIndex),
    )


@callback
def get_node_bindings(node: MatterNode, endpoint_id: int) -> list[BindingEntry]:
    """Get binding entries for a specific endpoint from cached node data.

    Reads the Binding cluster attribute from the already-cached MatterNode data.
    Returns an empty list if the endpoint does not exist or has no Binding cluster.
    """
    endpoint = node.endpoints.get(endpoint_id)
    if endpoint is None:
        return []

    if not endpoint.has_attribute(None, clusters.Binding.Attributes.Binding):
        return []

    binding_list: list[clusters.Binding.Structs.TargetStruct] = (
        endpoint.get_attribute_value(None, clusters.Binding.Attributes.Binding) or []
    )

    return [_parse_binding_entry_typed(entry) for entry in binding_list]


@callback
def get_node_acl(node: MatterNode) -> list[ACLEntry]:
    """Get ACL entries from cached node data.

    Reads the AccessControl cluster attribute from endpoint 0 of the
    already-cached MatterNode data.
    Returns an empty list if the ACL attribute is not present.
    """
    endpoint = node.endpoints.get(0)
    if endpoint is None:
        return []

    if not endpoint.has_attribute(None, clusters.AccessControl.Attributes.Acl):
        return []

    acl_list: list[clusters.AccessControl.Structs.AccessControlEntryStruct] = (
        endpoint.get_attribute_value(None, clusters.AccessControl.Attributes.Acl) or []
    )

    return [_parse_acl_entry_typed(entry) for entry in acl_list]


async def async_read_node_bindings(
    matter_client: MatterClient,
    node_id: int,
    endpoint_id: int,
) -> list[BindingEntry]:
    """Read binding entries from a device by querying the Matter server.

    Performs a live read of the Binding cluster attribute, returning fresh data
    rather than cached values.
    """
    attribute_path = f"{endpoint_id}/{_BINDING_CLUSTER_ID}/{_BINDING_ATTRIBUTE_ID}"
    result = await matter_client.read_attribute(node_id, attribute_path)

    raw_entries: list[dict[str, Any]] = result.get(attribute_path, [])
    return [_parse_binding_entry_raw(entry) for entry in raw_entries]


async def async_read_node_acl(
    matter_client: MatterClient,
    node_id: int,
) -> list[ACLEntry]:
    """Read ACL entries from a device by querying the Matter server.

    Performs a live read of the AccessControl cluster attribute on endpoint 0,
    returning fresh data rather than cached values.
    """
    attribute_path = f"0/{_ACL_CLUSTER_ID}/{_ACL_ATTRIBUTE_ID}"
    result = await matter_client.read_attribute(node_id, attribute_path)

    raw_entries: list[dict[str, Any]] = result.get(attribute_path, [])
    return [_parse_acl_entry_raw(entry) for entry in raw_entries]
