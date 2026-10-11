"""Test importing Thread datasets from Matter border routers."""

from base64 import b64encode
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from freezegun.api import FrozenDateTimeFactory
from matter_server.common.errors import NodeNotReady
from matter_server.common.models import EventType
import pytest

from homeassistant.components.matter.adapter import THREAD_DATASET_RETRY_DELAY
from homeassistant.components.matter.thread_border_router import async_import_dataset
from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.common import async_fire_time_changed
from tests.components.thread import DATASET_1, DATASET_2


@pytest.fixture(autouse=True)
def short_border_agent_discovery_timeout() -> Generator[None]:
    """Keep the dataset store's 30 s discovery wait out of these tests.

    Every import starts _set_preferred_dataset_if_only_network, and test
    teardown waits for it; the wait is the thread integration's concern, not
    this one's.
    """
    # Zero rather than merely small: under a frozen clock a nonzero asyncio
    # timeout never elapses on its own.
    with patch.object(dataset_store, "BORDER_AGENT_DISCOVERY_TIMEOUT", 0):
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


async def test_coexists_with_the_otbr_integration(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """Importing over Matter must not disturb a dataset the otbr integration owns.

    Both integrations write to the same store. The otbr integration reaches a
    border router over its REST API, this one reaches it over Matter, and a user
    can have both.
    """
    await async_add_dataset(
        hass,
        "otbr",
        DATASET_TLV.hex(),
        preferred_border_agent_id="aabbccddeeff00112233445566778899",
        preferred_extended_address="8877665544332211",
    )

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    store = await dataset_store.async_get_store(hass)
    entries = list(store.datasets.values())

    # The same network must not be stored twice just because a second
    # integration reported it.
    assert len(entries) == 1

    entry = entries[0]
    assert entry.source == "otbr"
    # A different border router must not take over the preference. The Matter
    # node reports its own border agent, which is not the one otbr registered.
    assert entry.preferred_border_agent_id == "aabbccddeeff00112233445566778899"
    assert entry.preferred_extended_address == "8877665544332211"


async def test_dataset_read_retried_after_node_not_ready(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A read failing with NodeNotReady is retried after the node settles.

    The failed read must not count as done: the timestamp is forgotten, so
    the delayed retry actually re-reads instead of deduplicating itself away.
    """
    # Seed a preferred dataset up front: with a preference in place the store
    # skips its border-agent discovery task, whose wait never elapses under
    # this test's frozen clock.
    await async_add_dataset(hass, "test", DATASET_2)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    assert len(store.datasets) == 1

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET_TLV).decode()
    }

    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(store.datasets) == 2
    matter_entry = next(e for e in store.datasets.values() if e.source == "matter")
    assert matter_entry.tlv == DATASET_TLV.hex()


async def test_dataset_retry_cancelled_on_unload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading the entry cancels a pending NodeNotReady retry."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads_before_unload = matter_client.send_device_command.call_count

    entry = hass.config_entries.async_entries("matter")[0]
    assert await hass.config_entries.async_unload(entry.entry_id)

    matter_client.send_device_command.side_effect = None
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert matter_client.send_device_command.call_count == reads_before_unload
    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0


async def test_endpoint_removal_forgets_import_state(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """ENDPOINT_REMOVED releases the bookkeeping for that border router.

    With the subscription and timestamp gone, the same node re-announcing an
    unchanged dataset is read again instead of deduplicated against state of
    an endpoint that no longer exists.
    """
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads = matter_client.send_device_command.call_count
    assert reads > 0

    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.ENDPOINT_REMOVED,
        data={"node_id": node.node_id, "endpoint_id": 1},
    )
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_count == reads + 1


async def test_node_removal_forgets_import_state(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """NODE_REMOVED cleans up every endpoint of the node."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads = matter_client.send_device_command.call_count

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_REMOVED, data=node.node_id
    )
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_ADDED, data=node
    )
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_count == reads + 1


async def test_node_removal_after_client_eviction_forgets_import_state(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """The import state goes even when the client already evicted the node."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads = matter_client.send_device_command.call_count

    original_get_node = matter_client.get_node.side_effect
    matter_client.get_node.side_effect = KeyError(node.node_id)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_REMOVED, data=node.node_id
    )
    matter_client.get_node.side_effect = original_get_node

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_ADDED, data=node
    )
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_count == reads + 1


async def test_retry_skipped_when_node_removed_meanwhile(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pending retry whose node is gone by firing time does nothing."""
    await async_add_dataset(hass, "test", DATASET_2)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads = matter_client.send_device_command.call_count

    original_get_node = matter_client.get_node.side_effect
    matter_client.get_node.side_effect = KeyError(node.node_id)
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    matter_client.get_node.side_effect = original_get_node

    assert matter_client.send_device_command.call_count == reads
    assert len(store.datasets) == 1


async def test_retry_rearmed_not_duplicated(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second failure while a retry is pending replaces the timer.

    One timer per endpoint: when the delay finally elapses there is exactly
    one retry read, not one per earlier failure.
    """
    await async_add_dataset(hass, "test", DATASET_2)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done()
    reads_while_failing = matter_client.send_device_command.call_count

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET_TLV).decode()
    }
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert matter_client.send_device_command.call_count == reads_while_failing + 1
    assert len(store.datasets) == 2


async def test_unusable_dataset_responses_are_skipped(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Non-dict, undecodable and raw-bytes response shapes are all handled."""
    endpoint = MagicMock()
    endpoint.node.node_id = 1
    endpoint.endpoint_id = 1
    endpoint.get_attribute_value.side_effect = lambda _, attr: {
        clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID: b"\x01" * 16,
        clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress: 0x1122334455667788,
    }[attr]

    with patch(
        "homeassistant.components.matter.thread_border_router.async_add_dataset"
    ) as add_dataset:
        # Malformed responses raise so the adapter does not consider the
        # import done: an object without a usable dataset attribute, a string
        # that is not base64, and non-alphabet characters prefixed to an
        # otherwise valid value (the default decoder would silently discard
        # them and import the corrupted remainder).
        for malformed in (
            SimpleNamespace(dataset=None),
            {"dataset": "%%%not-base64%%%"},
            {"dataset": "!" + b64encode(DATASET_TLV).decode()},
        ):
            matter_client.send_device_command = AsyncMock(return_value=malformed)
            with pytest.raises(ValueError):
                await async_import_dataset(hass, matter_client, endpoint)
        add_dataset.assert_not_called()

        # Raw bytes are accepted as they are.
        matter_client.send_device_command = AsyncMock(
            return_value={"dataset": DATASET_TLV}
        )
        await async_import_dataset(hass, matter_client, endpoint)
        add_dataset.assert_called_once()


async def test_offline_border_router_not_polled(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unavailable node is not read, and a pending retry stops on it.

    Without the availability gate every NodeNotReady retry re-arms itself, so
    a cached offline border router would be polled every retry interval
    indefinitely.
    """
    await async_add_dataset(hass, "test", DATASET_2)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    reads = matter_client.send_device_command.call_count

    node.node_data.available = False
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert matter_client.send_device_command.call_count == reads

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET_TLV).decode()
    }
    node.node_data.available = True
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done()
    assert len(store.datasets) == 2


async def test_malformed_response_is_retried_on_next_trigger(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A malformed response must not count as done for the timestamp.

    Unlike a legitimately empty dataset, it leaves nothing imported and the
    next trigger re-reads instead of deduplicating against the cached state.
    """
    matter_client.send_device_command.return_value = {"dataset": "%%%not-base64%%%"}
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 0

    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET_TLV).decode()
    }
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done()
    assert len(store.datasets) == 1
