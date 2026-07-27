"""Test importing Thread datasets from Matter border routers."""

import asyncio
from base64 import b64encode
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.models import device_types
from matter_server.common.models import EventType
import pytest

from homeassistant.components.matter.thread_border_router import async_store_dataset
from homeassistant.components.thread import dataset_store
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.components.thread import DATASET_1, DATASET_2


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


def _dataset_reads(matter_client: MagicMock) -> int:
    """Return how often the active dataset was requested."""
    return sum(
        isinstance(
            call.kwargs.get("command"),
            clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
        )
        for call in matter_client.send_device_command.call_args_list
    )


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


@pytest.mark.parametrize(
    "device_type",
    [
        device_types.NetworkInfrastructureManager.device_type,
        device_types.ThreadBorderRouter.device_type,
    ],
)
async def test_dataset_imported_from_border_router(
    hass: HomeAssistant,
    matter_client: MagicMock,
    dataset_response: dict[str, str],
    device_type: int,
) -> None:
    """A border router's active dataset is added to the Thread dataset store."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/29/0": [{"0": device_type, "1": 1}]},
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
    assert _dataset_reads(matter_client) == 1

    # A node update with an unchanged dataset must not cause another read.
    set_node_attribute(node, 1, 1106, 3, False)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert _dataset_reads(matter_client) == 1

    # A new active dataset timestamp must.
    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert _dataset_reads(matter_client) == 2


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
    assert _dataset_reads(matter_client) == 1

    # An event without a timestamp change must not cause a read. (The test
    # helper fires every subscription, not just the one for the path.)
    await trigger_subscription_callback(
        hass, matter_client, EventType.ATTRIBUTE_UPDATED, None
    )
    assert _dataset_reads(matter_client) == 1

    # A pushed ActiveDatasetTimestamp change must.
    set_node_attribute(node, 1, 1106, 4, 3)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        3,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    assert _dataset_reads(matter_client) == 2


async def test_dataset_reread_on_extended_address_update(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A new extended address under the same dataset is read and stored."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    set_node_attribute(node, 1, 53, 63, 0x8877665544332211)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        0x8877665544332211,
        node_id=node.node_id,
        attribute_path="1/53/63",
    )

    assert _dataset_reads(matter_client) == 2
    store = await dataset_store.async_get_store(hass)
    (entry,) = store.datasets.values()
    assert entry.preferred_extended_address == "8877665544332211"


async def test_dataset_changed_during_a_read_is_read_again(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A change while a read is in flight is read again once that read ends.

    A server can merge an identical command into the read in flight, which may
    answer with the dataset just replaced: that answer is dropped, not stored.
    """
    answer = asyncio.Event()
    answers = [DATASET_1, DATASET_2]

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return {"dataset": b64encode(bytes.fromhex(answers.pop(0))).decode()}

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == 1

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    assert _dataset_reads(matter_client) == 1

    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 2
    store = await dataset_store.async_get_store(hass)
    assert [entry.tlv for entry in store.datasets.values()] == [DATASET_2.lower()]


async def test_the_store_is_loaded_before_the_read(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Storing the answer does not wait for the store to load.

    A change arriving during that wait would slip in between the check for one
    and the add.
    """
    loaded_at_read: list[bool] = []

    async def read(**kwargs: Any) -> dict[str, str]:
        loaded_at_read.append(
            isinstance(
                hass.data.get(dataset_store.DATA_STORE), dataset_store.DatasetStore
            )
        )
        return {"dataset": b64encode(DATASET_TLV).decode()}

    matter_client.send_device_command.side_effect = read
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    assert loaded_at_read == [True]


async def test_null_ext_address_omits_preference_pair(hass: HomeAssistant) -> None:
    """A border router with no Thread stack reports ExtAddress as NullValue.

    NullValue is neither None nor falsy, so it has to be excluded explicitly or
    the store raises for a border agent ID without an extended address.
    """
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
        await async_store_dataset(hass, endpoint, DATASET_TLV)

    add_dataset.assert_called_once()
    kwargs = add_dataset.call_args.kwargs
    assert "preferred_border_agent_id" not in kwargs
    assert "preferred_extended_address" not in kwargs
