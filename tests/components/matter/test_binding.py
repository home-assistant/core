"""Test the Matter binding module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.matter.binding import (
    ACLEntry,
    ACLTarget,
    BindingEntry,
    async_read_node_acl,
    async_read_node_bindings,
    get_node_acl,
    get_node_bindings,
)

from .common import create_node_from_fixture

# --- Cached binding tests ---


def test_get_node_bindings_empty() -> None:
    """Test that an endpoint with Binding cluster but no entries returns empty list."""
    node = create_node_from_fixture("silabs_light_switch")
    result = get_node_bindings(node, 1)
    assert result == []


def test_get_node_bindings_nonexistent_endpoint() -> None:
    """Test that a nonexistent endpoint returns empty list."""
    node = create_node_from_fixture("silabs_light_switch")
    result = get_node_bindings(node, 99)
    assert result == []


def test_get_node_bindings_no_binding_cluster() -> None:
    """Test that an endpoint without Binding cluster returns empty list."""
    node = create_node_from_fixture("mock_dimmable_light")
    result = get_node_bindings(node, 1)
    assert result == []


def test_get_node_bindings_with_entries() -> None:
    """Test parsing binding entries from cached node data."""
    node = create_node_from_fixture(
        "silabs_light_switch",
        override_attributes={
            "1/30/0": [
                {
                    "1": 42,
                    "2": None,
                    "3": 1,
                    "4": 6,
                    "254": 1,
                },
                {
                    "1": 43,
                    "2": None,
                    "3": 2,
                    "4": 768,
                    "254": 1,
                },
            ],
        },
    )
    result = get_node_bindings(node, 1)

    assert len(result) == 2
    assert result[0] == BindingEntry(
        node_id=42,
        group_id=None,
        endpoint_id=1,
        cluster_id=6,
        fabric_index=1,
    )
    assert result[1] == BindingEntry(
        node_id=43,
        group_id=None,
        endpoint_id=2,
        cluster_id=768,
        fabric_index=1,
    )


def test_get_node_bindings_group_binding() -> None:
    """Test parsing a group binding entry."""
    node = create_node_from_fixture(
        "silabs_light_switch",
        override_attributes={
            "1/30/0": [
                {
                    "1": None,
                    "2": 5,
                    "3": None,
                    "4": None,
                    "254": 1,
                },
            ],
        },
    )
    result = get_node_bindings(node, 1)

    assert len(result) == 1
    assert result[0] == BindingEntry(
        node_id=None,
        group_id=5,
        endpoint_id=None,
        cluster_id=None,
        fabric_index=1,
    )


# --- Cached ACL tests ---


def test_get_node_acl_basic() -> None:
    """Test reading ACL from fixture with one admin entry."""
    node = create_node_from_fixture("silabs_light_switch")
    result = get_node_acl(node)

    assert len(result) == 1
    assert result[0] == ACLEntry(
        privilege=5,
        auth_mode=2,
        subjects=(112233,),
        targets=(),
        fabric_index=3,
    )


def test_get_node_acl_with_targets() -> None:
    """Test reading ACL entries with target constraints."""
    node = create_node_from_fixture(
        "silabs_light_switch",
        override_attributes={
            "0/31/0": [
                {
                    "1": 3,
                    "2": 2,
                    "3": [100, 200],
                    "4": [
                        {"0": 6, "1": 1, "2": None},
                        {"0": None, "1": None, "2": 256},
                    ],
                    "254": 1,
                },
            ],
        },
    )
    result = get_node_acl(node)

    assert len(result) == 1
    entry = result[0]
    assert entry.privilege == 3
    assert entry.auth_mode == 2
    assert entry.subjects == (100, 200)
    assert len(entry.targets) == 2
    assert entry.targets[0] == ACLTarget(
        cluster_id=6, endpoint_id=1, device_type_id=None
    )
    assert entry.targets[1] == ACLTarget(
        cluster_id=None, endpoint_id=None, device_type_id=256
    )
    assert entry.fabric_index == 1


def test_get_node_acl_multiple_entries() -> None:
    """Test reading multiple ACL entries."""
    node = create_node_from_fixture(
        "silabs_light_switch",
        override_attributes={
            "0/31/0": [
                {
                    "1": 5,
                    "2": 2,
                    "3": [112233],
                    "4": None,
                    "254": 1,
                },
                {
                    "1": 3,
                    "2": 2,
                    "3": [445566],
                    "4": None,
                    "254": 1,
                },
            ],
        },
    )
    result = get_node_acl(node)

    assert len(result) == 2
    assert result[0].privilege == 5
    assert result[0].subjects == (112233,)
    assert result[1].privilege == 3
    assert result[1].subjects == (445566,)


def test_get_node_acl_no_endpoint_zero() -> None:
    """Test that a node without endpoint 0 returns empty list."""
    node = create_node_from_fixture("silabs_light_switch")
    # Remove endpoint 0 to simulate missing root endpoint
    del node.endpoints[0]
    result = get_node_acl(node)
    assert result == []


# --- Fresh read binding tests ---


async def test_async_read_node_bindings_empty(matter_client: MagicMock) -> None:
    """Test reading bindings that returns empty list."""
    matter_client.read_attribute = AsyncMock(return_value={"1/30/0": []})

    result = await async_read_node_bindings(matter_client, 42, 1)
    assert result == []
    matter_client.read_attribute.assert_awaited_once_with(42, "1/30/0")


async def test_async_read_node_bindings_with_entries(
    matter_client: MagicMock,
) -> None:
    """Test reading and parsing binding entries from device."""
    matter_client.read_attribute = AsyncMock(
        return_value={
            "1/30/0": [
                {
                    "1": 10,
                    "2": None,
                    "3": 1,
                    "4": 6,
                    "254": 2,
                },
                {
                    "1": None,
                    "2": 7,
                    "3": None,
                    "4": None,
                    "254": 2,
                },
            ],
        }
    )

    result = await async_read_node_bindings(matter_client, 42, 1)

    assert len(result) == 2
    assert result[0] == BindingEntry(
        node_id=10,
        group_id=None,
        endpoint_id=1,
        cluster_id=6,
        fabric_index=2,
    )
    assert result[1] == BindingEntry(
        node_id=None,
        group_id=7,
        endpoint_id=None,
        cluster_id=None,
        fabric_index=2,
    )


async def test_async_read_node_bindings_missing_path(
    matter_client: MagicMock,
) -> None:
    """Test reading bindings when attribute path is missing returns empty list."""
    matter_client.read_attribute = AsyncMock(return_value={})

    result = await async_read_node_bindings(matter_client, 42, 1)
    assert result == []


# --- Fresh read ACL tests ---


async def test_async_read_node_acl_basic(matter_client: MagicMock) -> None:
    """Test reading a single ACL entry from device."""
    matter_client.read_attribute = AsyncMock(
        return_value={
            "0/31/0": [
                {
                    "1": 5,
                    "2": 2,
                    "3": [112233],
                    "4": None,
                    "254": 1,
                },
            ],
        }
    )

    result = await async_read_node_acl(matter_client, 42)

    assert len(result) == 1
    assert result[0] == ACLEntry(
        privilege=5,
        auth_mode=2,
        subjects=(112233,),
        targets=(),
        fabric_index=1,
    )
    matter_client.read_attribute.assert_awaited_once_with(42, "0/31/0")


async def test_async_read_node_acl_empty(matter_client: MagicMock) -> None:
    """Test reading ACL that returns empty list."""
    matter_client.read_attribute = AsyncMock(return_value={"0/31/0": []})

    result = await async_read_node_acl(matter_client, 42)
    assert result == []


async def test_async_read_node_acl_missing_path(matter_client: MagicMock) -> None:
    """Test reading ACL when attribute path is missing returns empty list."""
    matter_client.read_attribute = AsyncMock(return_value={})

    result = await async_read_node_acl(matter_client, 42)
    assert result == []


async def test_async_read_node_acl_with_targets(matter_client: MagicMock) -> None:
    """Test reading ACL with target constraints via read_attribute."""
    matter_client.read_attribute = AsyncMock(
        return_value={
            "0/31/0": [
                {
                    "1": 3,
                    "2": 2,
                    "3": [100, 200],
                    "4": [
                        {"0": 6, "1": 1, "2": None},
                        {"0": None, "1": None, "2": 256},
                    ],
                    "254": 1,
                },
            ],
        }
    )

    result = await async_read_node_acl(matter_client, 42)

    assert len(result) == 1
    entry = result[0]
    assert entry.privilege == 3
    assert entry.subjects == (100, 200)
    assert len(entry.targets) == 2
    assert entry.targets[0] == ACLTarget(
        cluster_id=6, endpoint_id=1, device_type_id=None
    )
    assert entry.targets[1] == ACLTarget(
        cluster_id=None, endpoint_id=None, device_type_id=256
    )
