"""Test importing Thread datasets from Matter border routers."""

from base64 import b64encode
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.common.models import EventType
import pytest

from homeassistant.components.matter.thread_border_router import async_import_dataset
from homeassistant.components.thread import dataset_store
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.components.thread import DATASET_1


@pytest.fixture(autouse=True)
def short_border_agent_discovery_timeout() -> Generator[None]:
    """Keep the dataset store's 30 s discovery wait out of these tests.

    Every import starts _set_preferred_dataset_if_only_network, and test
    teardown waits for it; the wait is the thread integration's concern, not
    this one's.
    """
    with patch.object(dataset_store, "BORDER_AGENT_DISCOVERY_TIMEOUT", 0.05):
        yield


# Reuse a known-good dataset from the Thread integration's own tests; the store
# parses it and rejects anything lacking an active timestamp.
DATASET_TLV = bytes.fromhex(DATASET_1)

BORDER_AGENT_ID = "0102030405060708090a0b0c0d0e0f10"
EXT_ADDRESS_HEX = "1122334455667788"


@pytest.fixture(autouse=True)
def mock_thread_discovery(mock_async_zeroconf: MagicMock) -> MagicMock:
    """Adding a dataset starts Thread discovery, which would open a real socket."""
    return mock_async_zeroconf


@pytest.fixture(name="dataset_response")
def dataset_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make GetActiveDatasetRequest return a dataset.

    The Matter client returns command responses as dicts with octet strings
    base64 encoded, which is what a real border router produces.
    """
    response = {"dataset": b64encode(DATASET_TLV).decode()}
    matter_client.send_device_command.return_value = response
    return response


async def test_dataset_imported_from_border_router(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A border router's active dataset is added to the Thread dataset store."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    # The dataset is only reachable by command, not as an attribute.
    assert matter_client.send_device_command.called
    command = matter_client.send_device_command.call_args.kwargs["command"]
    assert isinstance(
        command,
        clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
    )

    store = await dataset_store.async_get_store(hass)
    entries = list(store.datasets.values())
    assert len(entries) == 1

    entry = entries[0]
    assert entry.source == "matter"
    assert entry.tlv == DATASET_TLV.hex()
    # Both preference fields must be set together, or the store raises.
    assert entry.preferred_border_agent_id == BORDER_AGENT_ID
    assert entry.preferred_extended_address == EXT_ADDRESS_HEX


async def test_empty_dataset_is_not_imported(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """An unprovisioned border router returns an empty dataset and is skipped."""
    matter_client.send_device_command.return_value = {"dataset": ""}

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0


async def test_non_border_router_node_is_ignored(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A node without the TBRM cluster never triggers a dataset read."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    await hass.async_block_till_done()

    for call in matter_client.send_device_command.call_args_list:
        assert not isinstance(
            call.kwargs.get("command"),
            clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
        )

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0


async def test_dataset_not_reread_when_timestamp_unchanged(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """Node updates must not re-issue the command while the dataset is unchanged."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    def dataset_reads() -> int:
        return sum(
            isinstance(
                call.kwargs.get("command"),
                clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
            )
            for call in matter_client.send_device_command.call_args_list
        )

    assert dataset_reads() == 1

    # A node update with an unchanged dataset must not cause another read.
    set_node_attribute(node, 1, 1106, 3, False)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert dataset_reads() == 1

    # A new active dataset timestamp must.
    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert dataset_reads() == 2


async def test_dataset_reread_on_attribute_update(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A pushed timestamp change re-imports without waiting for an interview.

    Scheduled migrations change the dataset while the node is otherwise quiet:
    the device reports the new ActiveDatasetTimestamp through the attribute
    subscription, and no interview happens.
    """
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    def dataset_reads() -> int:
        return sum(
            isinstance(
                call.kwargs.get("command"),
                clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
            )
            for call in matter_client.send_device_command.call_args_list
        )

    assert dataset_reads() == 1

    # An event without a timestamp change must not cause a read. (The real
    # client only dispatches this callback for the subscribed attribute path;
    # the test helper fires every subscription, so this also exercises the
    # timestamp bookkeeping.)
    await trigger_subscription_callback(
        hass, matter_client, EventType.ATTRIBUTE_UPDATED, None
    )
    assert dataset_reads() == 1

    # A pushed ActiveDatasetTimestamp change must.
    set_node_attribute(node, 1, 1106, 4, 3)
    await trigger_subscription_callback(
        hass, matter_client, EventType.ATTRIBUTE_UPDATED, 3
    )
    assert dataset_reads() == 2


async def test_null_ext_address_omits_preference_pair(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A border router with no Thread stack reports ExtAddress as NullValue.

    NullValue is neither None nor falsy, so it has to be excluded explicitly or
    the store raises for a border agent ID without an extended address.
    """
    matter_client.send_device_command = AsyncMock(
        return_value={"dataset": b64encode(DATASET_TLV).decode()}
    )

    endpoint = MagicMock()
    endpoint.node.node_id = 1
    endpoint.endpoint_id = 1
    endpoint.get_attribute_value.side_effect = lambda _, attr: {
        clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID: b"\x01" * 16,
        clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress: NullValue,
    }[attr]

    with patch(
        "homeassistant.components.matter.thread_border_router.async_add_dataset"
    ) as add_dataset:
        await async_import_dataset(hass, matter_client, endpoint)

    add_dataset.assert_called_once()
    kwargs = add_dataset.call_args.kwargs
    assert "preferred_border_agent_id" not in kwargs
    assert "preferred_extended_address" not in kwargs
