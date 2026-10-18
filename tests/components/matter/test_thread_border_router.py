"""Test the Thread dataset import from Matter border routers."""

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
from pytest_homeassistant.common import MockConfigEntry
from python_otbr_api import tlv_parser

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.matter.thread_border_router import async_store_dataset
from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.components.thread import DATASET_1


@pytest.fixture(autouse=True)
def short_border_agent_discovery_timeout() -> Generator[None]:
    """Skip the store's 30 s border agent discovery wait, which never elapses under a frozen clock."""
    with patch.object(dataset_store, "BORDER_AGENT_DISCOVERY_TIMEOUT", 0):
        yield


@pytest.fixture(autouse=True)
def mock_thread_discovery(mock_async_zeroconf: MagicMock) -> MagicMock:
    """Adding a dataset starts Thread discovery, which would open a real socket."""
    return mock_async_zeroconf


def _with_timestamp(dataset: str, seconds: int) -> bytes:
    """Return a dataset with its active timestamp replaced."""
    items = tlv_parser.parse_tlv(dataset)
    items[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=seconds
    )
    return bytes.fromhex(tlv_parser.encode_tlv(items))


# The fixture's border router is on DATASET_1's network.
DATASET_TLV = bytes.fromhex(DATASET_1)
DATASET_NEWER = _with_timestamp(DATASET_1, 2)
DATASET_NEWEST = _with_timestamp(DATASET_1, 3)
NETWORK = "1111111122222222"

BORDER_AGENT_ID = "0102030405060708090a0b0c0d0e0f10"
EXT_ADDRESS_HEX = "1122334455667788"


def _response(dataset: bytes) -> dict[str, str]:
    """Return a DatasetResponse as the client delivers it."""
    return {"dataset": b64encode(dataset).decode()}


def _dataset_reads(matter_client: MagicMock) -> int:
    """Return how often the active dataset was requested."""
    return sum(
        isinstance(
            call.kwargs.get("command"),
            clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
        )
        for call in matter_client.send_device_command.call_args_list
    )


def _import_button(hass: HomeAssistant) -> str | None:
    """Return the entity id of the import button, if there is one."""
    return next(
        (
            entry.entity_id
            for entry in er.async_get(hass).entities.values()
            if entry.platform == "matter"
            and "ThreadDatasetImportButton" in entry.unique_id
        ),
        None,
    )


async def _press_import(hass: HomeAssistant) -> None:
    """Press the import button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _import_button(hass)},
        blocking=True,
    )


async def _stored(hass: HomeAssistant) -> dataset_store.DatasetEntry | None:
    """Return the stored dataset of the router's network."""
    store = await dataset_store.async_get_store(hass)
    return next(
        (
            entry
            for entry in store.datasets.values()
            if entry.extended_pan_id == NETWORK
        ),
        None,
    )


@pytest.fixture(name="dataset_response")
def dataset_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make GetActiveDatasetRequest return DATASET_1."""
    response = _response(DATASET_TLV)
    matter_client.send_device_command.return_value = response
    return response


@pytest.fixture(name="newer_response")
def newer_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make GetActiveDatasetRequest return a newer DATASET_1."""
    response = _response(DATASET_NEWER)
    matter_client.send_device_command.return_value = response
    return response


@pytest.fixture(name="known_network")
async def known_network_fixture(hass: HomeAssistant) -> None:
    """Have the store hold the router's network already, from another source."""
    await async_add_dataset(hass, "test", DATASET_1)


@pytest.fixture(name="imported_network")
async def imported_network_fixture(hass: HomeAssistant) -> None:
    """Have the store hold the router's network from an earlier import here."""
    await async_add_dataset(hass, "matter", DATASET_1)


async def test_border_router_is_not_read_without_a_press(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A border router of an unknown network is left alone until the user imports it."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    assert _dataset_reads(matter_client) == 0
    assert await _stored(hass) is None
    assert not hass.config_entries.async_entries("thread")


@pytest.mark.parametrize(
    "device_type",
    [
        device_types.NetworkInfrastructureManager.device_type,
        device_types.ThreadBorderRouter.device_type,
    ],
)
async def test_import_button_for_both_border_router_device_types(
    hass: HomeAssistant, matter_client: MagicMock, device_type: int
) -> None:
    """Both border router device types get the import button."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/29/0": [{"0": device_type, "1": 1}]},
    )

    assert _import_button(hass) is not None


async def test_no_import_button_without_a_border_router(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A node without the TBRM cluster has no import button."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert _import_button(hass) is None


async def test_pressing_the_button_imports_the_dataset(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """The button reads the dataset by command and adds it to the store."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _press_import(hass)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.source == "matter"
    assert entry.tlv == DATASET_TLV.hex()
    assert entry.preferred_border_agent_id == BORDER_AGENT_ID
    assert entry.preferred_extended_address == EXT_ADDRESS_HEX


async def test_the_first_import_sets_up_the_thread_integration(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """Thread is set up by the first import, once."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    assert "thread" not in hass.config.components

    await _press_import(hass)
    assert len(hass.config_entries.async_entries("thread")) == 1
    assert "thread" in hass.config.components

    await _press_import(hass)
    assert len(hass.config_entries.async_entries("thread")) == 1


async def test_an_existing_thread_entry_is_left_alone(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """An import does not add a Thread entry next to one that exists."""
    MockConfigEntry(domain="thread").add_to_hass(hass)
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _press_import(hass)

    assert len(hass.config_entries.async_entries("thread")) == 1
    assert await _stored(hass) is not None


async def test_an_unprovisioned_router_cannot_be_imported(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router without a network answers with an empty dataset; the press fails."""
    matter_client.send_device_command.return_value = {"dataset": ""}
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "thread_network_missing"
    assert await _stored(hass) is None
    assert not hass.config_entries.async_entries("thread")


async def test_an_imported_network_follows_its_router(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """After the import, a new active dataset timestamp is read; an unchanged one is not."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await _press_import(hass)
    assert _dataset_reads(matter_client) == 1

    set_node_attribute(node, 1, 1106, 3, False)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert _dataset_reads(matter_client) == 1

    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


async def test_a_router_of_an_unknown_network_is_not_followed(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """Without an import, a dataset change on the router is not read."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 0
    assert await _stored(hass) is None


async def test_a_network_imported_later_is_followed(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A router skipped for an unknown network is read once the network is imported here."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 0

    await async_add_dataset(hass, "matter", DATASET_1)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.source == "matter"
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network")
async def test_a_network_known_from_elsewhere_is_not_followed(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A router of a network stored from another source is not read without a press."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 0
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_1
    assert entry.preferred_border_agent_id is None


@pytest.mark.usefixtures("imported_network")
async def test_following_sets_no_preferred_border_agent(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A follow read updates the dataset but makes no router the preferred one."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()
    assert entry.preferred_border_agent_id is None
    assert entry.preferred_extended_address is None


async def test_dataset_reread_on_extended_address_update(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A new extended address under the same dataset is read and stored."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await _press_import(hass)

    set_node_attribute(node, 1, 53, 63, 0x8877665544332211)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        0x8877665544332211,
        node_id=node.node_id,
        attribute_path="1/53/63",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.preferred_extended_address == "8877665544332211"


@pytest.mark.usefixtures("imported_network")
async def test_dataset_changed_during_a_read_is_read_again(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A change during a read is read once that read ends."""
    answer = asyncio.Event()
    answers = [DATASET_NEWER, DATASET_NEWEST]

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(answers.pop(0))

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
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWEST.hex()


@pytest.mark.usefixtures("imported_network")
async def test_the_store_is_loaded_before_the_read(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The store is loaded when the command is sent, so the add does not wait."""
    loaded_at_read: list[bool] = []

    async def read(**kwargs: Any) -> dict[str, str]:
        loaded_at_read.append(
            isinstance(
                hass.data.get(dataset_store.DATA_STORE), dataset_store.DatasetStore
            )
        )
        return _response(DATASET_NEWER)

    matter_client.send_device_command.side_effect = read
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert loaded_at_read == [True]


@pytest.mark.parametrize("ext_address", [NullValue, -1, 1 << 64])
async def test_an_unusable_ext_address_omits_preference_pair(
    hass: HomeAssistant, ext_address: Any
) -> None:
    """An ExtAddress that is null (no Thread stack) or out of range is left out."""
    endpoint = MagicMock()
    endpoint.node.node_id = 1
    endpoint.endpoint_id = 1
    endpoint.get_attribute_value.side_effect = lambda _, attr: {
        clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID: b"\x01" * 16,
        clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress: ext_address,
    }[attr]

    with (
        patch(
            "homeassistant.components.matter.thread_border_router.async_add_dataset"
        ) as add_dataset,
        patch(
            "homeassistant.components.matter.thread_border_router.async_ensure_thread_setup"
        ),
    ):
        await async_store_dataset(hass, endpoint, DATASET_TLV)

    add_dataset.assert_called_once()
    kwargs = add_dataset.call_args.kwargs
    assert "preferred_border_agent_id" not in kwargs
    assert "preferred_extended_address" not in kwargs
